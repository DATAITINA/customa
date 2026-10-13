"""A plate counts only after a real scan of the stand's QR code.

The QR code carries a scan code (services/qr.py). Opening the stand page any other way (a
bookmark, the browser history, a shared link, a refresh) shows the card but counts nothing.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account_action, customer_action, user_action, visit_action
from app.core.config import settings
from app.models import CharacterCreate, Visit
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting

SLUG = "qr-scan-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
SIX_HOURS = 6 * 60 * 60
VENDOR_AUTH = {"Authorization": "Bearer *"}


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="QR Scan Stand",
        description="Test stand",
        character=CharacterCreate(name="Pot", menu=[{"item": "Jollof rice", "price": 1500}]),
        slug=SLUG,
    )
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    session.commit()
    return workspace


def code(session: Session, stand) -> str:
    return scan_code(stand, resolve_stand_settings(session, stand))


def count(client: TestClient, scan: str | None, key: str | None = None):
    body = {"consent": True, "first_name": "Ada"}
    if scan is not None:
        body["scan"] = scan
    return client.post(f"{BASE}/visits", json=body, headers={"X-Customer-Key": key} if key else None)


def six_hours_later(session: Session, key: str) -> None:
    customer = customer_action.get_by_all(session, key=key)
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=SIX_HOURS)
    session.add(visit)
    session.commit()


def plates(session: Session) -> int:
    session.expire_all()
    return len(session.exec(Visit.__table__.select()).all())


def test_no_scan_counts_nothing(client: TestClient, session: Session, stand) -> None:
    r = count(client, None)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "scan_required"
    assert count(client, "not-the-code").status_code == 403
    assert plates(session) == 0


def test_a_real_scan_counts(client: TestClient, session: Session, stand) -> None:
    r = count(client, code(session, stand))
    assert r.status_code == 200, r.text
    assert r.json()["plate_number"] == 1


def test_coming_back_without_a_scan_counts_nothing(client: TestClient, session: Session, stand) -> None:
    key = count(client, code(session, stand)).json()["customer"]["key"]
    six_hours_later(session, key)
    # Opening the page again from a bookmark: the timer is done, but no scan, no plate.
    assert count(client, None, key).status_code == 403
    assert plates(session) == 1
    # Scanning the QR at the stand counts the next plate.
    r = count(client, code(session, stand), key)
    assert r.status_code == 200 and r.json()["plate_number"] == 2


def test_new_qr_turns_old_prints_off(client: TestClient, session: Session, stand) -> None:
    old = code(session, stand)
    r = client.get(f"{VENDOR}/qr", headers=VENDOR_AUTH)
    assert r.status_code == 200 and r.json()["scan"] == old

    r = client.post(f"{VENDOR}/qr/new", headers=VENDOR_AUTH)
    assert r.status_code == 200
    new = r.json()["scan"]
    assert new != old and r.json()["version"] == 2

    assert count(client, old).status_code == 403
    assert count(client, new).status_code == 200


def test_scan_code_is_for_stand_members_only(client: TestClient, stand) -> None:
    assert client.get(f"{VENDOR}/qr").status_code == 401
    assert client.post(f"{VENDOR}/qr/new").status_code == 401


def test_scan_codes_differ_between_stands(session: Session, stand) -> None:
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    other, _ = create_stand(
        session, owner=owner, name="Other Stand", description="x",
        character=CharacterCreate(name="Cup"), slug="other-qr-stand",
    )
    session.commit()
    assert code(session, stand) != code(session, other)


def test_prepaid_plate_needs_a_scan(client: TestClient, session: Session, stand) -> None:
    for key, value in (
        ("PLATE_AJO_ENABLED", True),
        ("AJO_BANK_NAME", "Opay"),
        ("AJO_ACCOUNT_NUMBER", "8031234567"),
        ("AJO_ACCOUNT_NAME", "Mama Pot"),
    ):
        set_stand_setting(session, stand, key, value)
    session.commit()
    key = count(client, code(session, stand)).json()["customer"]["key"]
    who = {"X-Customer-Key": key}
    r = client.post(
        f"{BASE}/ajo/bundles",
        json={"item": "Jollof rice", "plates": 5, "payer_name": "Ada"},
        headers=who,
    )
    assert r.status_code == 200, r.text
    bundle_id = r.json()["bundle"]["id"]
    assert client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=VENDOR_AUTH).status_code == 200

    r = client.post(f"{BASE}/ajo/use", headers=who)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "scan_required"
    r = client.post(f"{BASE}/ajo/use", json={"scan": code(session, stand)}, headers=who)
    assert r.status_code == 200, r.text
