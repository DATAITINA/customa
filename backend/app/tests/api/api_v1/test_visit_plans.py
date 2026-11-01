"""Plan the next visit through the real API and the service: making, changing and cancelling a
plan, the calendar file, kept and missed plans, reminders (push, SMS behind the stand setting,
never twice), the scheduler's secret, the vendor's numbers and the 14-day return rate."""

import base64
from datetime import UTC, date, datetime, timedelta

import pytest
import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, customer_action, user_action, visit_action
from app.core.config import settings
from app.models import CharacterCreate, Customer, SmsSubscription, Visit, VisitPlan
from app.services import insights, sms_alerts, visit_plans
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting
from app.services.visit_plans import local_today, when_text, window

SLUG = "plans-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
CRON = f"{settings.API_V1_STR}/cron/plan-reminders"
AUTH = {"Authorization": "Bearer *"}


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Thursday", description="Test stand",
        character=CharacterCreate(name="Ekaette Pot", body="pot", color="palm", accessory="chef"), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def first_plate(client: TestClient, session: Session, stand, name: str | None = "Ada") -> dict:
    body = {"consent": True, "scan": scan_code(stand, resolve_stand_settings(session, stand))}
    if name:
        body["first_name"] = name
    r = client.post(f"{BASE}/visits", json=body)
    assert r.status_code == 200, r.text
    return {"X-Customer-Key": r.json()["customer"]["key"]}


def customer_of(session: Session, headers: dict):
    return customer_action.get_by_all(session, key=headers["X-Customer-Key"])


def plan(client: TestClient, headers: dict, day: date, slot: str):
    return client.put(f"{BASE}/plan", json={"day": day.isoformat(), "slot": slot}, headers=headers)


def tomorrow() -> date:
    return local_today(utcnow()) + timedelta(days=1)


def test_words_and_slots() -> None:
    today = date(2026, 10, 15)  # a Thursday
    assert when_text(today, "lunch", today) == "today for lunch"
    assert when_text(today, "evening", today) == "this evening"
    assert when_text(today + timedelta(days=1), "morning", today) == "tomorrow morning"
    assert when_text(today + timedelta(days=7), "lunch", today) == "Thursday for lunch"
    start, end = window(today, "lunch")  # 11:00-15:00 Nigeria time = 10:00-14:00 UTC
    assert (start.hour, end.hour) == (10, 14)


def test_options_offer_today_tomorrow_and_six_days(client: TestClient, session: Session, stand) -> None:
    ada = first_plate(client, session, stand)
    opts = client.get(f"{BASE}/plan", headers=ada).json()["options"]
    labels = [d["label"] for d in opts["days"]]
    assert labels[-7] == "Tomorrow" and len(labels) in (7, 8)  # today too, unless all its slots are over
    assert [s["key"] for s in opts["slots"]] == ["morning", "lunch", "evening"]
    assert client.get(f"{BASE}/plan").status_code == 404  # needs the customer's key


def test_make_change_cancel(client: TestClient, session: Session, stand) -> None:
    ada = first_plate(client, session, stand)
    r = plan(client, ada, tomorrow(), "lunch")
    assert r.status_code == 200, r.text
    p = r.json()["plan"]
    assert p["slot"] == "lunch" and p["confirm"] == "Deal! I go dey expect you tomorrow for lunch 🙌"
    assert "reservation" not in str(r.json()).lower()

    # Both a day and a time are needed; only the next week; nothing in the past.
    assert client.put(f"{BASE}/plan", json={"day": tomorrow().isoformat()}, headers=ada).status_code == 422
    assert plan(client, ada, tomorrow(), "midnight").status_code == 400
    assert plan(client, ada, tomorrow() + timedelta(days=10), "lunch").status_code == 400
    assert plan(client, ada, local_today(utcnow()) - timedelta(days=1), "lunch").status_code == 400

    # Changing keeps one active plan.
    assert plan(client, ada, tomorrow(), "evening").json()["plan"]["slot"] == "evening"
    statuses = [p.status for p in session.exec(select(VisitPlan).order_by(VisitPlan.id)).all()]
    assert statuses == ["cancelled", "active"]

    assert client.delete(f"{BASE}/plan", headers=ada).json()["plan"] is None


def test_calendar_file(client: TestClient, session: Session, stand) -> None:
    ada = first_plate(client, session, stand)
    plan(client, ada, tomorrow(), "lunch")
    r = client.get(f"{BASE}/plan.ics", params={"k": ada["X-Customer-Key"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.text
    start, end = window(tomorrow(), "lunch")
    assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in body and f"DTEND:{end:%Y%m%dT%H%M%SZ}" in body
    assert "TRIGGER:-PT1H" in body and "SUMMARY:Lunch at Mama Thursday" in body and "not a booking" in body
    assert client.get(f"{BASE}/plan.ics", params={"k": "wrong-key"}).status_code == 404


def test_kept_and_missed(client: TestClient, session: Session, stand) -> None:
    ada = first_plate(client, session, stand)
    customer = customer_of(session, ada)
    plan(client, ada, tomorrow(), "lunch")
    start, _ = window(tomorrow(), "lunch")
    visit = visit_action.last_for_customer(session, customer_id=customer.id)

    # A plate during the slot keeps it.
    visit_plans.on_plate_counted(session, customer=customer, visit=visit, now=start + timedelta(hours=1))
    assert visit_plans.outcome_for_visit(session, visit) == "kept"

    # Next plan missed: told once, at the next plate ("No wahala").
    plan(client, ada, tomorrow(), "evening")
    _, evening_end = window(tomorrow(), "evening")
    visit_plans.run_reminders(session, now=evening_end + timedelta(hours=2))  # the scheduler marks it missed
    assert session.exec(select(VisitPlan).where(VisitPlan.slot == "evening")).one().status == "missed"
    later = Visit(workspace_id=stand.id, customer_id=customer.id, plate_number=2)
    session.add(later)
    session.commit()
    visit_plans.on_plate_counted(session, customer=customer, visit=later, now=evening_end + timedelta(days=1))
    assert visit_plans.outcome_for_visit(session, later) == "missed"


def test_scan_response_says_kept(client: TestClient, session: Session, stand, monkeypatch) -> None:
    """Through the real scan: a plate in the planned slot keeps the plan."""
    ada = first_plate(client, session, stand)
    customer = customer_of(session, ada)
    plan(client, ada, tomorrow(), "lunch")
    # The slot is happening now (the real windows depend on the clock).
    now = utcnow()
    monkeypatch.setattr(visit_plans, "window", lambda day, slot: (now - timedelta(hours=1), now + timedelta(hours=1)))
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = now - timedelta(hours=7)
    session.add(visit)
    session.commit()
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": scan}, headers=ada)
    assert r.json()["plan_outcome"] == "kept"
    assert session.exec(select(VisitPlan)).one().status == "kept"


@pytest.fixture
def vapid(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", b64url(public))
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", b64url(key.private_numbers().private_value.to_bytes(32, "big")))


@pytest.fixture
def push_service(monkeypatch):
    calls: list[dict] = []

    class Response:
        status_code = 201
        text = ""
        reason = ""

    def post(url, data=None, headers=None, timeout=None, **_):
        calls.append({"url": url})
        return Response()

    monkeypatch.setattr(pywebpush.requests, "post", post)
    return calls


def phone() -> dict:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"endpoint": "https://fcm.googleapis.com/fcm/send/ada", "keys": {"p256dh": b64url(public), "auth": b64url(b"0123456789abcdef")}}


def test_push_reminder_once(client: TestClient, session: Session, stand, vapid, push_service) -> None:
    ada = first_plate(client, session, stand)
    client.post(f"{BASE}/alerts", json=phone(), headers=ada)
    r = plan(client, ada, tomorrow(), "lunch").json()
    assert r["plan"]["reminder"] == "push"
    due = session.exec(select(VisitPlan)).one().reminder_due_at
    assert due == window(tomorrow(), "lunch")[0] - timedelta(hours=1)

    assert visit_plans.run_reminders(session, now=due - timedelta(minutes=10))["push"] == 0
    assert visit_plans.run_reminders(session, now=due + timedelta(minutes=1))["push"] == 1
    assert len(push_service) == 1
    assert visit_plans.run_reminders(session, now=due + timedelta(minutes=16))["push"] == 0  # never twice
    assert len(push_service) == 1


def test_sms_reminder_only_when_allowed(client: TestClient, session: Session, stand, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TERMII_API_KEY", "k")
    monkeypatch.setattr(settings, "TERMII_SENDER_ID", "Customa")
    texts: list[dict] = []

    class Ok:
        status_code = 200
        text = "{}"

    monkeypatch.setattr(sms_alerts.requests, "post", lambda url, json=None, timeout=None, **_: texts.append(json) or Ok())
    ada = first_plate(client, session, stand)
    client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}, headers=ada)

    # Texts agreed, but the stand has SMS reminders off (the default): no text.
    assert plan(client, ada, tomorrow(), "lunch").json()["plan"]["reminder"] is None
    due = session.exec(select(VisitPlan).where(VisitPlan.status == "active")).one().reminder_due_at
    assert visit_plans.run_reminders(session, now=due + timedelta(minutes=1))["none"] == 1 and texts == []

    set_stand_setting(session, stand, "PLAN_SMS_REMINDERS", True)
    session.commit()
    assert plan(client, ada, tomorrow(), "evening").json()["plan"]["reminder"] == "sms"
    due = session.exec(select(VisitPlan).where(VisitPlan.status == "active")).one().reminder_due_at
    assert visit_plans.run_reminders(session, now=due + timedelta(minutes=1))["sms"] == 1
    (sent,) = texts
    assert sent["to"] == ["2348031234567"] and len(sent["sms"]) <= 160 and sent["sms"].isascii()
    assert "No pressure" in sent["sms"]

    # Without the customer's agreement to texts: never a text.
    session.delete(session.exec(select(SmsSubscription)).one())
    session.commit()
    assert plan(client, ada, tomorrow(), "morning").json()["plan"]["reminder"] is None


def test_scheduler_needs_the_secret(client: TestClient, monkeypatch) -> None:
    assert client.get(CRON).status_code == 503  # no secret set: refuse everything
    monkeypatch.setattr(settings, "CRON_SECRET", "s3cret")
    assert client.get(CRON).status_code == 401
    assert client.get(CRON, headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = client.get(CRON, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and set(r.json()) == {"push", "sms", "none", "missed"}


def test_vendor_numbers(client: TestClient, session: Session, stand) -> None:
    ada, anon = first_plate(client, session, stand), first_plate(client, session, stand, name=None)
    today = local_today(utcnow())
    for headers, slot in ((ada, "lunch"), (anon, "evening")):
        session.add(VisitPlan(workspace_id=stand.id, customer_id=customer_of(session, headers).id, day=today, slot=slot))
    session.add(VisitPlan(workspace_id=stand.id, customer_id=customer_of(session, ada).id, day=today - timedelta(days=2), slot="lunch", status="kept"))
    session.add(VisitPlan(workspace_id=stand.id, customer_id=customer_of(session, anon).id, day=today - timedelta(days=3), slot="lunch", status="missed"))
    session.commit()
    plans = client.get(f"{VENDOR}/dashboard", headers=AUTH).json()["plans"]
    coming = plans["coming_today"]
    if coming["total"] == 2:  # both today's slots still ahead (the test can run late at night)
        assert coming["by_slot"] == {"morning": 0, "lunch": 1, "evening": 1}
        assert coming["names"] == [{"name": "Ada", "slot": "lunch", "came": False}]  # no name, no entry
    assert plans["kept_week"]["kept"] == 1 and plans["kept_week"]["total"] >= 2


def test_return_rate_from_real_visits(session: Session, stand) -> None:
    now = utcnow()

    def customer(*days_ago: int) -> None:
        c = Customer(workspace_id=stand.id, key=f"k{days_ago}{len(days_ago)}", consent=True)
        session.add(c)
        session.commit()
        for n, d in enumerate(days_ago, start=1):
            session.add(Visit(workspace_id=stand.id, customer_id=c.id, plate_number=n, created_at=now - timedelta(days=d)))
        session.commit()

    customer(20, 15)  # came back 5 days after the first plate
    customer(30)  # never came back
    customer(40, 10)  # came back, but after 30 days: not within 14
    customer(3, 1)  # first plate too recent to count
    r = insights.return_rate(session, workspace=stand, now=now)
    assert (r["percent"], r["returned"], r["customers"]) == (33, 1, 3)
    assert sum(w["customers"] for w in r["weeks"]) == 3


def test_delete_my_data_removes_plans(client: TestClient, session: Session, stand) -> None:
    ada = first_plate(client, session, stand)
    plan(client, ada, tomorrow(), "lunch")
    assert client.delete(f"{BASE}/me", headers=ada).status_code == 200
    session.expire_all()
    assert session.exec(select(VisitPlan)).all() == []
