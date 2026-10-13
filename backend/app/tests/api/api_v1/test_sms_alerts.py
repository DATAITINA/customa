"""Leftover-food alerts by text message (Termii) through the real API.

Termii is never called: `requests.post` in services/sms_alerts.py is replaced and records each
bulk request.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, SmsSubscription
from app.services import sms_alerts
from app.services.qr import scan_code
from app.services.sms_alerts import last_plates_text, normalize_phone
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting

SLUG = "texts-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
VENDOR_AUTH = {"Authorization": "Bearer *"}


@pytest.fixture
def termii(monkeypatch):
    monkeypatch.setattr(settings, "TERMII_API_KEY", "test-key")
    monkeypatch.setattr(settings, "TERMII_SENDER_ID", "Customa")
    calls: list[dict] = []

    class Response:
        status_code = 200
        text = '{"code":"ok"}'

    def post(url, json=None, timeout=None, **_):
        calls.append({"url": url, "json": json})
        return Response()

    monkeypatch.setattr(sms_alerts.requests, "post", post)
    return calls


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Mama Ekaette's Kitchen",
        description="Test stand",
        character=CharacterCreate(name="Ekaette Pot", body="pot", color="palm", accessory="chef"),
        slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def customer(client: TestClient, session: Session, stand) -> dict:
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    r = client.post(f"{BASE}/visits", json={"consent": True, "first_name": "Ada", "scan": scan})
    assert r.status_code == 200, r.text
    return {"X-Customer-Key": r.json()["customer"]["key"]}


def announce(client: TestClient, plates: int = 12) -> dict:
    r = client.post(f"{VENDOR}/last-plates", json={"plates_left": plates, "minutes": 90}, headers=VENDOR_AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def test_phone_numbers() -> None:
    for raw in ("08031234567", "0803 123 4567", "+234 803 123 4567", "2348031234567", "8031234567", "+234 0803 123 4567"):
        assert normalize_phone(raw) == "2348031234567", raw
    for raw in ("12345", "0803123456", "01234567890", "+44 7700 900123", "", "0803-123-4567-99"):
        assert normalize_phone(raw) is None, raw


def test_not_offered_without_termii(client: TestClient, stand) -> None:
    info = client.get(f"{BASE}/alerts").json()
    assert info["sms"] is False and info["sms_terms"] is None
    assert client.get(BASE).json()["features"]["alerts"] is False


def test_turn_on_texts_then_get_one(client: TestClient, session: Session, stand, termii) -> None:
    info = client.get(f"{BASE}/alerts").json()
    assert info["sms"] is True and "Mama Ekaette's Kitchen" in info["sms_terms"] and info["texting"] is None
    assert client.get(BASE).json()["features"]["alerts"] is True

    ada = customer(client, session, stand)
    r = client.post(f"{BASE}/alerts/sms", json={"phone": "0803 123 4567", "agree": True}, headers=ada)
    assert r.status_code == 200, r.text
    assert r.json() == {"texting": "0803 ••• 4567"}
    assert client.get(f"{BASE}/alerts", headers=ada).json()["texting"] == "0803 ••• 4567"
    # The vendor sees a count, never the number.
    dash = client.get(f"{VENDOR}/dashboard", headers=VENDOR_AUTH).json()
    assert dash["alert_subscribers"] == 1 and "2348031234567" not in str(dash)

    assert announce(client, 12)["alert"] == {"sent": 1, "texts": 1, "skipped": None}
    (call,) = termii
    assert call["url"] == "https://api.ng.termii.com/api/sms/send/bulk"
    body = call["json"]
    assert body["to"] == ["2348031234567"] and body["from"] == "Customa" and body["api_key"] == "test-key"
    assert body["type"] == "plain" and body["channel"] == "dnd"
    assert body["sms"].startswith("Ekaette at Mama Ekaette's Kitchen: last plates tonight! Only 12 plates left.")
    assert body["sms"].endswith(f"customa-web.vercel.app/s/{SLUG}") and len(body["sms"]) <= 160

    # Same once-an-hour limit as push alerts.
    assert announce(client, 4)["alert"]["skipped"] == "recently_alerted" and len(termii) == 1


def test_must_agree_and_be_a_customer(client: TestClient, session: Session, stand, termii) -> None:
    assert client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}).status_code == 404
    ada = customer(client, session, stand)
    assert client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": False}, headers=ada).status_code == 422
    assert client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567"}, headers=ada).status_code == 422
    r = client.post(f"{BASE}/alerts/sms", json={"phone": "12345678", "agree": True}, headers=ada)
    assert r.status_code == 400 and "Nigerian" in r.json()["detail"]


def test_one_number_per_card_and_per_stand(client: TestClient, session: Session, stand, termii) -> None:
    ada, ben = customer(client, session, stand), customer(client, session, stand)
    client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}, headers=ada)
    # Ada changes her number: still one row.
    client.post(f"{BASE}/alerts/sms", json={"phone": "09051234567", "agree": True}, headers=ada)
    # The same number on another card moves there, so nobody gets two texts.
    client.post(f"{BASE}/alerts/sms", json={"phone": "09051234567", "agree": True}, headers=ben)
    session.expire_all()
    rows = session.exec(select(SmsSubscription)).all()
    assert [r.phone for r in rows] == ["2349051234567"]
    assert client.get(f"{BASE}/alerts", headers=ada).json()["texting"] is None


def test_stand_limit(client: TestClient, session: Session, stand, termii) -> None:
    set_stand_setting(session, stand, "SMS_MAX_SUBSCRIBERS", 1)
    session.commit()
    ada, ben = customer(client, session, stand), customer(client, session, stand)
    assert client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}, headers=ada).status_code == 200
    r = client.post(f"{BASE}/alerts/sms", json={"phone": "08039999999", "agree": True}, headers=ben)
    assert r.status_code == 400 and "full" in r.json()["detail"]


def test_stop_texts_and_delete_my_data(client: TestClient, session: Session, stand, termii) -> None:
    ada = customer(client, session, stand)
    client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}, headers=ada)
    assert client.post(f"{BASE}/alerts/sms/off", headers=ada).json() == {"texting": None}
    session.expire_all()
    assert session.exec(select(SmsSubscription)).all() == []

    client.post(f"{BASE}/alerts/sms", json={"phone": "08031234567", "agree": True}, headers=ada)
    assert client.delete(f"{BASE}/me", headers=ada).status_code == 200
    session.expire_all()
    assert session.exec(select(SmsSubscription)).all() == []
    assert announce(client)["alert"]["skipped"] == "no_subscribers" and termii == []


def test_text_is_one_plain_page(stand) -> None:
    stand.name = "Mama Ekaette’s Very Famous Afang 🍲 & Edikang Ikong Kitchen by the Roundabout"
    character = CharacterCreate(name="Ekaette Pot", body="pot", color="palm", accessory="chef")
    text = last_plates_text(workspace=stand, character=character, plates_left=1, until_label="8:30 PM")
    assert len(text) <= 160 and text.isascii()
    assert "Only 1 plate left. Come before 8:30 PM." in text and text.endswith(f"/s/{SLUG}")
