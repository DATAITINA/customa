"""Save your card / "Already have a card?" through the real API: link a number, recover the card
in a new browser, wrong PINs, lockouts, unknown numbers, SMS codes, and the plate window."""

import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, CustomerPhone, RecoveryAttempt
from app.services import sms_alerts
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings

SLUG = "card-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
AUTH = {"Authorization": "Bearer *"}
PHONE = "0803 123 4521"
PIN = "2580"


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Card", description="Test stand",
        character=CharacterCreate(name="Card Pot", body="pot", color="palm", accessory="chef",
                                  menu=[{"item": "Jollof rice", "price": 2000}]), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def plate(client: TestClient, session: Session, stand, headers: dict | None = None, name: str | None = "Ada"):
    body = {"consent": True, "scan": scan_code(stand, resolve_stand_settings(session, stand))}
    if name:
        body["first_name"] = name
    return client.post(f"{BASE}/visits", json=body, headers=headers or {})


@pytest.fixture
def browser_a(client, session, stand) -> dict:
    """Browser A: scanned once (plate 1) and saved the card to a number."""
    r = plate(client, session, stand)
    assert r.status_code == 200, r.text
    headers = {"X-Customer-Key": r.json()["customer"]["key"]}
    r = client.put(f"{BASE}/card/phone", json={"phone": PHONE, "pin": PIN}, headers=headers)
    assert r.status_code == 200, r.text
    return headers


def recover(client, phone=PHONE, pin=PIN, headers=None, code=None):
    body = {"phone": phone, **({"code": code} if code else {"pin": pin})}
    return client.post(f"{BASE}/card/recover", json=body, headers=headers or {})


def test_link_shows_only_a_masked_number(client, session, stand, browser_a):
    s = client.get(f"{BASE}/card", headers=browser_a).json()
    assert s == {"enabled": True, "linked": True, "masked": "0803 ••• 4521", "sms": sms_alerts.sms_available()}
    row = session.exec(select(CustomerPhone)).one()
    assert "8031234521" not in json.dumps(row.model_dump(mode="json")) and row.pin_hash != PIN
    # The vendor sees a "saved" mark, never the number.
    d = client.get(f"{VENDOR}/dashboard", headers=AUTH).json()
    assert d["recent_visits"][0]["saved"] is True
    assert "4521" not in json.dumps(d) and "803" not in json.dumps(d["recent_visits"])


def test_recover_in_a_new_browser_gets_the_same_card(client, session, stand, browser_a):
    r = recover(client)
    assert r.status_code == 200, r.text
    new_key = r.json()["key"]
    assert new_key != browser_a["X-Customer-Key"]
    browser_b = {"X-Customer-Key": new_key}
    me = client.get(BASE, headers=browser_b).json()["customer"]
    assert me["plate_number"] == 1 and me["first_name"] == "Ada"
    assert me["key"] == new_key  # browser B keeps its own key, never browser A's
    # Browser A still works.
    assert client.get(BASE, headers=browser_a).json()["customer"]["plate_number"] == 1
    assert session.exec(select(RecoveryAttempt).where(RecoveryAttempt.kind == "pin", RecoveryAttempt.outcome == "ok")).one()


def test_no_extra_plate_inside_the_window_after_recovery(client, session, stand, browser_a):
    browser_b = {"X-Customer-Key": recover(client).json()["key"]}
    r = plate(client, session, stand, headers=browser_b)
    assert r.status_code == 409 and r.json()["detail"]["seconds_left"] > 0


def test_a_plate_on_the_old_card_still_holds_the_window(client, session, stand, browser_a):
    """Browser B first scanned as a stranger (a new card, plate 1), then got the real card back:
    no second plate in the same window on the real card."""
    from datetime import UTC, datetime, timedelta

    from app.models import Visit

    # The real card's plate is old: on its own it would allow a new plate now.
    for v in session.exec(select(Visit)).all():
        v.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=7)
        session.add(v)
    session.commit()
    r = plate(client, session, stand, name=None)  # browser B, no key: a brand-new card
    stranger = {"X-Customer-Key": r.json()["customer"]["key"]}
    browser_b = {"X-Customer-Key": recover(client, headers=stranger).json()["key"]}
    r = plate(client, session, stand, headers=browser_b)
    assert r.status_code == 409


def test_wrong_pin_and_lockout(client, stand, browser_a):
    for _ in range(5):
        r = recover(client, pin="9753")
        assert r.status_code == 400 and "don't match" in r.json()["detail"]
    r = recover(client)  # the right PIN, but the number is locked now
    assert r.status_code == 429 and "minutes" in r.json()["detail"]


def test_unknown_number_reveals_nothing(client, stand, browser_a):
    wrong_known = recover(client, pin="9753")
    unknown = recover(client, phone="0809 999 0000", pin="9753")
    assert (unknown.status_code, unknown.json()) == (wrong_known.status_code, wrong_known.json())
    # Unknown numbers lock out the same way.
    for _ in range(4):
        recover(client, phone="0809 999 0000", pin="9753")
    assert recover(client, phone="0809 999 0000", pin="9753").status_code == 429


def test_a_number_never_moves_from_someone_elses_card(client, session, stand, browser_a):
    r = plate(client, session, stand, name="Bola")
    other = {"X-Customer-Key": r.json()["customer"]["key"]}
    r = client.put(f"{BASE}/card/phone", json={"phone": PHONE, "pin": "1357"}, headers=other)
    assert r.status_code == 409
    # Ada's PIN still works; Bola's doesn't.
    assert recover(client, pin="1357").status_code == 400
    assert recover(client).status_code == 200


def test_weak_and_malformed_input(client, stand, browser_a):
    assert client.put(f"{BASE}/card/phone", json={"phone": PHONE, "pin": "1111"}, headers=browser_a).status_code == 400
    assert client.put(f"{BASE}/card/phone", json={"phone": "12345678", "pin": PIN}, headers=browser_a).status_code == 400
    assert client.post(f"{BASE}/card/recover", json={"phone": PHONE}).status_code == 400


def test_sms_code_when_texts_are_on(client, stand, browser_a, monkeypatch):
    monkeypatch.setattr(settings, "TERMII_API_KEY", "test")
    monkeypatch.setattr(settings, "TERMII_SENDER_ID", "Customa")
    sent: list[tuple[list[str], str]] = []
    monkeypatch.setattr(sms_alerts, "send_chunk", lambda chunk, text: sent.append((chunk, text)) or len(chunk))
    known = client.post(f"{BASE}/card/recover/code", json={"phone": PHONE})
    unknown = client.post(f"{BASE}/card/recover/code", json={"phone": "0809 999 0000"})
    assert known.json() == unknown.json() and known.status_code == unknown.status_code == 200
    assert len(sent) == 1 and sent[0][0] == ["2348031234521"]
    code = re.search(r"\b(\d{6})\b", sent[0][1]).group(1)
    assert recover(client, code="000000" if code != "000000" else "111111").status_code == 400
    assert recover(client, code=code).status_code == 200
    assert recover(client, code=code).status_code == 400  # one use only


def test_delete_my_data_removes_the_link(client, session, stand, browser_a):
    browser_b = {"X-Customer-Key": recover(client).json()["key"]}
    assert client.delete(f"{BASE}/me", headers=browser_b).status_code == 200
    session.expire_all()
    assert session.exec(select(CustomerPhone)).all() == []
    assert recover(client).status_code == 400
