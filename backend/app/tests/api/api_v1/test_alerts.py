"""Leftover-food alerts (web push) through the real API.

The push service is never called: `requests.post` inside pywebpush is replaced, so these tests
also check the real encryption (the phone can decrypt the alert) and the VAPID signature.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import http_ece
import pytest
import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, PushSubscription
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting

SLUG = "alerts-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
VENDOR_AUTH = {"Authorization": "Bearer *"}
FCM = "https://fcm.googleapis.com/fcm/send/abc123"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Phone:
    """A browser's push keys, like PushManager.subscribe() makes them."""

    def __init__(self, endpoint: str = FCM) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = b"0123456789abcdef"
        self.endpoint = endpoint

    def subscription(self) -> dict:
        public = self.key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return {"endpoint": self.endpoint, "keys": {"p256dh": b64url(public), "auth": b64url(self.auth)}}

    def read(self, body: bytes) -> dict:
        return json.loads(http_ece.decrypt(body, private_key=self.key, auth_secret=self.auth, version="aes128gcm"))


@pytest.fixture
def vapid(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", b64url(public))
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", b64url(key.private_numbers().private_value.to_bytes(32, "big")))
    return key


class Sent:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = 201


@pytest.fixture
def push_service(monkeypatch):
    sent = Sent()

    class Response:
        def __init__(self, status: int) -> None:
            self.status_code = status
            self.text = ""
            self.reason = ""

    def post(url, data=None, headers=None, timeout=None, **_):
        sent.calls.append({"url": url, "data": data, "headers": headers})
        return Response(sent.status)

    monkeypatch.setattr(pywebpush.requests, "post", post)
    return sent


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
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
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


def test_not_offered_without_keys(client: TestClient, stand) -> None:
    assert client.get(f"{BASE}/alerts").json() == {"available": False, "public_key": None}


def test_turn_on_then_get_the_alert(client: TestClient, session: Session, stand, vapid, push_service) -> None:
    info = client.get(f"{BASE}/alerts").json()
    assert info["available"] is True and info["public_key"] == settings.VAPID_PUBLIC_KEY

    ada = customer(client, session, stand)
    phone = Phone()
    r = client.post(f"{BASE}/alerts", json=phone.subscription(), headers=ada)
    assert r.status_code == 200 and r.json() == {"subscribed": True}
    # Turning it on twice keeps one subscription.
    client.post(f"{BASE}/alerts", json=phone.subscription(), headers=ada)
    assert client.get(f"{VENDOR}/dashboard", headers=VENDOR_AUTH).json()["alert_subscribers"] == 1

    result = announce(client, 12)
    assert result["alert"] == {"sent": 1, "skipped": None}
    call = push_service.calls[0]
    assert call["url"] == FCM
    assert call["headers"]["Urgency"] == "high" and int(call["headers"]["ttl"]) > 0
    assert call["headers"]["Authorization"].startswith("vapid t=")

    message = phone.read(call["data"])
    assert message["title"] == "Ekaette: last plates tonight! 🍲"
    assert message["body"].startswith("Only 12 plates left at Mama Ekaette's Kitchen. Come chop before ")
    assert message["character"] == {"name": "Ekaette Pot", "body": "pot", "color": "palm", "accessory": "chef"}
    assert message["url"] == f"/s/{SLUG}" and message["tag"] == f"last-plates-{SLUG}"


def test_one_alert_per_hour(client: TestClient, session: Session, stand, vapid, push_service) -> None:
    ada = customer(client, session, stand)
    client.post(f"{BASE}/alerts", json=Phone().subscription(), headers=ada)
    assert announce(client)["alert"]["sent"] == 1
    assert announce(client, 5)["alert"] == {"sent": 0, "skipped": "recently_alerted"}
    # An hour later the vendor can alert again.
    set_stand_setting(
        session, stand, "LAST_PLATES_ALERTED_AT",
        (datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=61)).isoformat(timespec="seconds"),
    )
    session.commit()
    assert announce(client, 3)["alert"]["sent"] == 1
    # Ending the announcement sends nothing.
    assert announce(client, 0)["alert"]["skipped"] == "ended"


def test_phones_that_left_are_removed(client: TestClient, session: Session, stand, vapid, push_service) -> None:
    ada = customer(client, session, stand)
    client.post(f"{BASE}/alerts", json=Phone().subscription(), headers=ada)
    push_service.status = 410
    assert announce(client)["alert"]["sent"] == 0
    session.expire_all()
    assert session.exec(select(PushSubscription)).all() == []


def test_only_real_push_services(client: TestClient, session: Session, stand, vapid) -> None:
    ada = customer(client, session, stand)
    for endpoint in ("http://fcm.googleapis.com/x", "https://evil.example.com/push", "https://169.254.169.254/latest"):
        r = client.post(f"{BASE}/alerts", json=Phone(endpoint).subscription(), headers=ada)
        assert r.status_code == 400, endpoint
    apple = Phone("https://web.push.apple.com/QGuQyavXutnMH")
    assert client.post(f"{BASE}/alerts", json=apple.subscription(), headers=ada).status_code == 200


def test_needs_a_customer(client: TestClient, stand, vapid) -> None:
    assert client.post(f"{BASE}/alerts", json=Phone().subscription()).status_code == 404


def test_turn_off_and_delete_my_data(client: TestClient, session: Session, stand, vapid) -> None:
    ada = customer(client, session, stand)
    phone = Phone()
    client.post(f"{BASE}/alerts", json=phone.subscription(), headers=ada)
    r = client.post(f"{BASE}/alerts/off", json={"endpoint": phone.endpoint}, headers=ada)
    assert r.json() == {"subscribed": False}
    session.expire_all()
    assert session.exec(select(PushSubscription)).all() == []

    client.post(f"{BASE}/alerts", json=phone.subscription(), headers=ada)
    assert client.delete(f"{BASE}/me", headers=ada).status_code == 200
    session.expire_all()
    assert session.exec(select(PushSubscription)).all() == []
