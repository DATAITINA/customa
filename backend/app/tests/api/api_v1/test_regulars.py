"""Regular-arrived alert ("Ime don land!") through the real API: who's here now, greeted, the
vendor's phone ping (push service replaced), and the customer's own "my usual"."""

import base64
from datetime import UTC, datetime, timedelta

import pytest
import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, customer_action, user_action, visit_action
from app.core.config import settings
from app.models import Arrival, CharacterCreate, CustomerUsual
from app.services.qr import scan_code
from app.services.regulars import ago, ordinal
from app.services.stands import create_stand, resolve_stand_settings

SLUG = "regulars-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
AUTH = {"Authorization": "Bearer *"}
MENU = [{"item": "Afang soup", "price": 2500}, {"item": "Jollof rice", "price": 2000}]


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Ime", description="Test stand",
        character=CharacterCreate(name="Ime Pot", body="pot", color="palm", accessory="chef", menu=MENU), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def scan(session: Session, stand) -> str:
    return scan_code(stand, resolve_stand_settings(session, stand))


def first_plate(client: TestClient, session: Session, stand, name: str | None = "Ime") -> dict:
    body = {"consent": True, "scan": scan(session, stand)}
    if name:
        body["first_name"] = name
    r = client.post(f"{BASE}/visits", json=body)
    assert r.status_code == 200, r.text
    return {"X-Customer-Key": r.json()["customer"]["key"]}


def next_plate(client: TestClient, session: Session, stand, headers: dict, days_ago: int = 3) -> dict:
    customer = customer_action.get_by_all(session, key=headers["X-Customer-Key"])
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = utcnow() - timedelta(days=days_ago)
    session.add(visit)
    session.commit()
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": scan(session, stand)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def here_now(client: TestClient) -> list[dict]:
    return client.get(f"{VENDOR}/dashboard", headers=AUTH).json()["here_now"]


def test_words() -> None:
    assert [ordinal(n) for n in (1, 2, 3, 4, 9, 11, 12, 13, 21, 22, 101)] == [
        "1st", "2nd", "3rd", "4th", "9th", "11th", "12th", "13th", "21st", "22nd", "101st",
    ]
    now = datetime(2026, 10, 16, 13, 0, tzinfo=UTC).replace(tzinfo=None)
    assert ago(now - timedelta(hours=2), now) == "earlier today"
    assert ago(now - timedelta(days=1), now) == "yesterday"
    assert ago(now - timedelta(days=3), now) == "3 days ago"
    assert ago(now - timedelta(days=21), now) == "3 weeks ago"
    assert ago(None, now) is None


def test_new_face_then_regular(client: TestClient, session: Session, stand) -> None:
    ime = first_plate(client, session, stand)
    (entry,) = here_now(client)
    assert entry["name"] == "Ime" and entry["visit_number"] == 1 and entry["returning"] is False
    assert entry["visit_label"] == "New face: first plate 👋" and entry["last_came"] is None

    next_plate(client, session, stand, ime, days_ago=3)
    (entry,) = here_now(client)  # one entry per customer: their latest plate
    assert entry["visit_number"] == 2 and entry["visit_label"] == "2nd visit" and entry["returning"] is True
    assert entry["last_came"] == "3 days ago"
    assert entry["greeting"].startswith("Ime! Welcome back o!")
    # Privacy: only what staff need; no phone, no chat, no usual unless the customer shared it.
    assert set(entry) == {
        "id", "name", "visit_number", "visit_label", "returning", "last_came", "jara", "greeting", "usual", "at", "greeted_at",
    }
    assert entry["usual"] is None


def test_no_name_shows_a_regular_and_jara_status(client: TestClient, session: Session, stand) -> None:
    anon = first_plate(client, session, stand, name=None)
    for _ in range(4):
        next_plate(client, session, stand, anon, days_ago=1)
    (entry,) = here_now(client)
    assert entry["name"] is None and entry["visit_label"] == "5th visit"
    assert entry["jara"] == "next_is_jara" and "Our regular" in entry["greeting"] and "next plate na jara" in entry["greeting"]
    next_plate(client, session, stand, anon, days_ago=1)  # plate 6: a jara code
    assert here_now(client)[0]["jara"] == "has_jara"


def test_only_recent_arrivals_and_greeted(client: TestClient, session: Session, stand) -> None:
    ime = first_plate(client, session, stand)
    next_plate(client, session, stand, ime)
    entry = here_now(client)[0]
    r = client.post(f"{VENDOR}/arrivals/{entry['id']}/greeted", headers=AUTH)
    assert r.status_code == 200 and r.json()["greeted_at"]
    assert here_now(client)[0]["greeted_at"]
    assert client.post(f"{VENDOR}/arrivals/999999/greeted", headers=AUTH).status_code == 404
    assert client.post(f"{VENDOR}/arrivals/{entry['id']}/greeted").status_code == 401

    # Older than the window: no longer "here now", but kept for measuring.
    for arrival in session.exec(select(Arrival)).all():
        arrival.created_at = utcnow() - timedelta(hours=3)
        session.add(arrival)
    session.commit()
    assert here_now(client) == []
    assert len(session.exec(select(Arrival)).all()) == 2


def test_usual_is_the_customers_choice(client: TestClient, session: Session, stand) -> None:
    ime = first_plate(client, session, stand)
    r = client.get(f"{BASE}/usual", headers=ime).json()
    assert r == {"usual": None, "menu": ["Afang soup", "Jollof rice"]}
    assert client.put(f"{BASE}/usual", json={"item": "Pizza"}, headers=ime).status_code == 400
    assert client.put(f"{BASE}/usual", json={"item": "jollof rice"}, headers=ime).json() == {"usual": "Jollof rice"}
    next_plate(client, session, stand, ime)
    assert here_now(client)[0]["usual"] == "Jollof rice"

    assert client.delete(f"{BASE}/usual", headers=ime).json() == {"usual": None}
    assert here_now(client)[0]["usual"] is None
    assert client.get(f"{BASE}/usual").status_code == 404  # needs the customer's key


def test_delete_my_data_removes_arrivals_and_usual(client: TestClient, session: Session, stand) -> None:
    ime = first_plate(client, session, stand)
    client.put(f"{BASE}/usual", json={"item": "Afang soup"}, headers=ime)
    next_plate(client, session, stand, ime)
    assert client.delete(f"{BASE}/me", headers=ime).status_code == 200
    session.expire_all()
    assert session.exec(select(Arrival)).all() == [] and session.exec(select(CustomerUsual)).all() == []
    assert here_now(client) == []


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
        calls.append({"url": url, "headers": headers})
        return Response()

    monkeypatch.setattr(pywebpush.requests, "post", post)
    return calls


def vendor_phone() -> dict:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"endpoint": "https://fcm.googleapis.com/fcm/send/vendor-1", "keys": {"p256dh": b64url(public), "auth": b64url(b"0123456789abcdef")}}


def test_vendor_ping_for_regulars_only_once_per_visit(client: TestClient, session: Session, stand, vapid, push_service) -> None:
    info = client.get(f"{VENDOR}/arrivals/ping", headers=AUTH).json()
    assert info["available"] is True and info["phones"] == 0
    assert client.post(f"{VENDOR}/arrivals/ping", json=vendor_phone(), headers=AUTH).json() == {"subscribed": True}
    assert client.get(f"{VENDOR}/arrivals/ping", headers=AUTH).json()["phones"] == 1
    # Not for customers or strangers.
    assert client.post(f"{VENDOR}/arrivals/ping", json=vendor_phone()).status_code == 401

    ime = first_plate(client, session, stand)
    assert push_service == []  # a first-timer: no ping (the dashboard still shows them)
    next_plate(client, session, stand, ime)
    assert len(push_service) == 1 and push_service[0]["url"].endswith("vendor-1")
    arrival = session.exec(select(Arrival).order_by(Arrival.id.desc())).first()
    session.refresh(arrival)
    assert arrival.pinged_at is not None

    client.post(f"{VENDOR}/arrivals/ping/off", json={"endpoint": vendor_phone()["endpoint"]}, headers=AUTH)
    next_plate(client, session, stand, ime)
    assert len(push_service) == 1
