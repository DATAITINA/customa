"""Pay for a plate through the real API: cash the vendor confirms, Paystack in test mode (the
Paystack API replaced), the webhook signature, today's payments, and "Delete my data"."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
import requests
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, Payment, Visit
from app.services import paystack
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings

SLUG = "pay-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
AUTH = {"Authorization": "Bearer *"}
MENU = [{"item": "Afang soup", "price": 2500}, {"item": "Jollof rice", "price": 2000}]
TEST_KEY = "sk_test_unit_only"


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Pay", description="Test stand",
        character=CharacterCreate(name="Pay Pot", body="pot", color="palm", accessory="chef", menu=MENU), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


@pytest.fixture
def customer(client: TestClient, session: Session, stand) -> dict:
    """A customer whose first plate was counted 7 hours ago (so the next plate can be stamped)."""
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    r = client.post(f"{BASE}/visits", json={"consent": True, "first_name": "Ada", "scan": scan})
    assert r.status_code == 200, r.text
    for v in session.exec(select(Visit).where(Visit.workspace_id == stand.id)).all():
        v.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=7)
        session.add(v)
    session.commit()
    return {"X-Customer-Key": r.json()["customer"]["key"]}


def turn_on(client: TestClient) -> None:
    r = client.put(f"{VENDOR}/payments/settings", json={"enabled": True}, headers=AUTH)
    assert r.status_code == 200, r.text


class FakePaystack:
    """Stands in for api.paystack.co: records calls, answers like Paystack does."""

    def __init__(self, verify_status="success", amount=None, currency="NGN"):
        self.calls = []
        self.verify_status, self.amount, self.currency = verify_status, amount, currency

    def __call__(self, method, url, headers=None, timeout=None, json=None, **_):
        self.calls.append((method, url, json))
        assert headers["Authorization"] == f"Bearer {TEST_KEY}"
        resp = requests.Response()
        resp.status_code = 200
        if url.endswith("/transaction/initialize"):
            self.amount = self.amount if self.amount is not None else json["amount"]
            body = {"status": True, "data": {"authorization_url": "https://checkout.paystack.com/abc", "reference": json["reference"]}}
        else:
            body = {"status": True, "data": {"status": self.verify_status, "amount": self.amount, "currency": self.currency}}
        resp._content = __import__("json").dumps(body).encode()
        return resp


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", TEST_KEY)
    f = FakePaystack()
    monkeypatch.setattr(paystack.requests, "request", f)
    return f


def test_off_until_the_vendor_turns_it_on(client, stand, customer):
    assert client.get(BASE + "/pay", headers=customer).json()["enabled"] is False
    r = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "cash"}, headers=customer)
    assert r.status_code == 403


def test_cash_received_counts_the_plate_as_a_stamp(client, session, stand, customer):
    turn_on(client)
    r = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "cash"}, headers=customer)
    assert r.status_code == 200, r.text
    p = r.json()["payment"]
    assert p["amount"] == 2500 and p["status"] == "pending" and len(p["code"]) == 3
    assert client.get(BASE + "/pay", headers=customer).json()["pending_cash"]["id"] == p["id"]

    today = client.get(f"{VENDOR}/payments/today", headers=AUTH).json()
    assert [w["code"] for w in today["waiting_cash"]] == [p["code"]]
    assert today["waiting_cash"][0]["name"] == "Ada"

    r = client.post(f"{VENDOR}/payments/{p['id']}/cash-received", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["payment"]["status"] == "paid" and r.json()["payment"]["stamped"] is True
    assert len(session.exec(select(Visit).where(Visit.workspace_id == stand.id)).all()) == 2
    # Twice is refused.
    assert client.post(f"{VENDOR}/payments/{p['id']}/cash-received", headers=AUTH).status_code == 409

    today = client.get(f"{VENDOR}/payments/today", headers=AUTH).json()
    assert today["total"] == 2500 and today["count"] == 1 and today["by_method"]["cash"] == 2500
    assert today["waiting_cash"] == []


def test_price_comes_from_the_menu(client, stand, customer):
    turn_on(client)
    r = client.post(BASE + "/pay", json={"item": "Caviar", "method": "cash"}, headers=customer)
    assert r.status_code == 400 and "menu" in r.json()["detail"]


def test_paid_inside_six_hours_is_paid_but_not_stamped_twice(client, session, stand, customer):
    turn_on(client)
    p = client.post(BASE + "/pay", json={"item": "Jollof rice", "method": "cash"}, headers=customer).json()["payment"]
    client.post(f"{VENDOR}/payments/{p['id']}/cash-received", headers=AUTH)
    p2 = client.post(BASE + "/pay", json={"item": "Jollof rice", "method": "cash"}, headers=customer).json()["payment"]
    r = client.post(f"{VENDOR}/payments/{p2['id']}/cash-received", headers=AUTH)
    assert r.json()["payment"]["status"] == "paid" and r.json()["payment"]["stamped"] is False


def test_paystack_flow_is_verified_and_counted_once(client, session, stand, customer, fake):
    turn_on(client)
    assert client.get(BASE + "/pay", headers=customer).json()["card"] is True
    r = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "paystack"}, headers=customer)
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("https://checkout.paystack.com/")
    ref = r.json()["payment"]["reference"]
    init = fake.calls[0][2]
    assert init["amount"] == 250000 and init["currency"] == "NGN"
    assert init["callback_url"].endswith(f"/s/{SLUG}/paid")

    r = client.post(BASE + "/pay/confirm", json={"reference": ref})
    assert r.json()["payment"]["status"] == "paid" and r.json()["payment"]["stamped"] is True
    # The return page and the webhook may both confirm: still one stamp, one payment.
    client.post(BASE + "/pay/confirm", json={"reference": ref})
    assert len(session.exec(select(Visit).where(Visit.workspace_id == stand.id)).all()) == 2
    assert client.get(f"{VENDOR}/payments/today", headers=AUTH).json()["by_method"]["paystack"] == 2500


def test_paystack_amount_mismatch_is_refused(client, stand, customer, fake):
    turn_on(client)
    fake.amount = 100
    ref = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "paystack"}, headers=customer).json()["payment"]["reference"]
    r = client.post(BASE + "/pay/confirm", json={"reference": ref})
    assert r.status_code == 409


def test_live_keys_are_refused(client, stand, customer, monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_live_nope")
    assert "test mode" in paystack.key_problem()
    turn_on(client)
    assert client.get(BASE + "/pay", headers=customer).json()["card"] is False
    r = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "paystack"}, headers=customer)
    assert r.status_code == 503 and "cash" in r.json()["detail"]


def test_webhook_needs_a_valid_signature(client, session, stand, customer, fake):
    turn_on(client)
    ref = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "paystack"}, headers=customer).json()["payment"]["reference"]
    body = json.dumps({"event": "charge.success", "data": {"reference": ref}}).encode()
    url = f"{settings.API_V1_STR}/payments/paystack/webhook"
    assert client.post(url, content=body, headers={"x-paystack-signature": "bad"}).status_code == 401
    sig = hmac.new(TEST_KEY.encode(), body, hashlib.sha512).hexdigest()
    assert client.post(url, content=body, headers={"x-paystack-signature": sig}).status_code == 200
    assert session.exec(select(Payment).where(Payment.reference == ref)).one().status == "paid"


def test_delete_my_data_keeps_takings_without_the_customer(client, session, stand, customer):
    turn_on(client)
    paid = client.post(BASE + "/pay", json={"item": "Afang soup", "method": "cash"}, headers=customer).json()["payment"]
    client.post(f"{VENDOR}/payments/{paid['id']}/cash-received", headers=AUTH)
    client.post(BASE + "/pay", json={"item": "Jollof rice", "method": "cash"}, headers=customer)
    assert client.delete(BASE + "/me", headers=customer).status_code == 200
    session.expire_all()
    rows = session.exec(select(Payment).where(Payment.workspace_id == stand.id)).all()
    assert [(r.status, r.customer_id, r.visit_id) for r in rows] == [("paid", None, None)]
