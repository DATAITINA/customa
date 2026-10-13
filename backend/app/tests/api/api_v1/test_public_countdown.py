"""The wait between plates: the stand's window (6 hours) for every customer, however they arrived.

Uses a normal stand with the default 6-hour window.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account_action, customer_action, visit_action
from app.core.config import settings
from app.models import CharacterCreate, CustomerCreate, Visit
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings

SIX_HOURS = 6 * 60 * 60
SLUG = "mama-put-test"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
SCAN = ""  # the stand's QR scan code, set by the stand fixture


def utcnow() -> datetime:
    # Naive UTC, like the timestamps the app stores and compares.
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Mama Put Test",
        description="Test stand",
        character=CharacterCreate(name="Pot"),
        slug=SLUG,
    )
    session.commit()
    global SCAN
    SCAN = scan_code(workspace, resolve_stand_settings(session, workspace))
    return workspace


def sign_up(client: TestClient, **body) -> dict:
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": SCAN, **body})
    assert r.status_code == 200, r.text
    return r.json()


def scan_again(client: TestClient, key: str, **body):
    return client.post(
        f"{BASE}/visits", json={"consent": True, "scan": SCAN, **body}, headers={"X-Customer-Key": key}
    )


def move_last_visit_back(session: Session, key: str, seconds: int) -> None:
    """Pretend the customer's last plate was counted `seconds` ago."""
    customer = customer_action.get_by_all(session, key=key)
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = utcnow() - timedelta(seconds=seconds)
    session.add(visit)
    session.commit()


def test_normal_customer_gets_6_hours(client: TestClient, session: Session, stand) -> None:
    data = sign_up(client)
    assert data["customer"]["window_seconds"] == SIX_HOURS
    # Every plate now comes from a real QR scan, so every customer arrived by QR.
    assert customer_action.get_by_all(session, key=data["customer"]["key"]).source == "qr"

    r = scan_again(client, data["customer"]["key"])
    assert r.status_code == 409
    assert SIX_HOURS - 5 <= r.json()["detail"]["seconds_left"] <= SIX_HOURS + 1


def test_qr_customer_also_gets_6_hours(client: TestClient, session: Session, stand) -> None:
    # The QR scan is still saved (for vendor stats) but no longer shortens the wait.
    data = sign_up(client, source="qr")
    assert data["customer"]["window_seconds"] == SIX_HOURS
    assert customer_action.get_by_all(session, key=data["customer"]["key"]).source == "qr"

    r = scan_again(client, data["customer"]["key"], source="qr")
    assert r.status_code == 409
    assert SIX_HOURS - 5 <= r.json()["detail"]["seconds_left"] <= SIX_HOURS + 1
    assert r.json()["detail"]["customer"]["window_seconds"] == SIX_HOURS


def test_plates_2_3_4_each_need_6_hours(client: TestClient, session: Session, stand) -> None:
    key = sign_up(client, source="qr")["customer"]["key"]
    for plate in (2, 3, 4):
        # One minute short of six hours: still blocked, about a minute left.
        move_last_visit_back(session, key, SIX_HOURS - 60)
        r = scan_again(client, key)
        assert r.status_code == 409, f"plate {plate} counted too early"
        assert 55 <= r.json()["detail"]["seconds_left"] <= 62
        assert r.json()["detail"]["customer"]["plate_number"] == plate - 1

        # Six hours have passed: the next plate counts and the timer starts again.
        move_last_visit_back(session, key, SIX_HOURS)
        r = scan_again(client, key)
        assert r.status_code == 200, r.text
        assert r.json()["plate_number"] == plate

        r = scan_again(client, key)
        assert r.status_code == 409
        assert r.json()["detail"]["seconds_left"] > SIX_HOURS - 10


def test_jara_on_plate_6_then_back_to_1(client: TestClient, session: Session, stand) -> None:
    key = sign_up(client)["customer"]["key"]
    for plate in range(2, 7):
        move_last_visit_back(session, key, SIX_HOURS)
        r = scan_again(client, key)
        assert r.json()["plate_number"] == plate
    assert r.json()["jara"] is not None

    move_last_visit_back(session, key, SIX_HOURS)
    r = scan_again(client, key)
    assert r.json()["plate_number"] == 1
    assert r.json()["jara"] is None


def test_refresh_keeps_remaining_time(client: TestClient, session: Session, stand) -> None:
    key = sign_up(client)["customer"]["key"]
    move_last_visit_back(session, key, 2 * 60 * 60)

    # A refresh re-reads the stand and re-scans: the timer continues, it does not restart.
    page = client.get(BASE, headers={"X-Customer-Key": key}).json()
    assert page["customer"]["window_seconds"] == SIX_HOURS
    r = scan_again(client, key)
    assert r.status_code == 409
    four_hours = 4 * 60 * 60
    assert four_hours - 5 <= r.json()["detail"]["seconds_left"] <= four_hours + 1


def test_unknown_source_is_ignored(client: TestClient, session: Session, stand) -> None:
    data = sign_up(client, source="vip")
    assert data["customer"]["window_seconds"] == SIX_HOURS
    assert customer_action.get_by_all(session, key=data["customer"]["key"]).source == "qr"


def test_window_cannot_be_sent_by_client(client: TestClient, session: Session, stand) -> None:
    data = sign_up(client, window_seconds=1, PLATE_WINDOW_SECONDS=1)
    assert data["customer"]["window_seconds"] == SIX_HOURS
    r = scan_again(client, data["customer"]["key"], window_seconds=1)
    assert r.status_code == 409


def test_existing_customer_keeps_6_hours(client: TestClient, session: Session, stand) -> None:
    # A customer created before the source column existed has no saved source.
    customer = customer_action.create_for_stand(
        session, workspace_id=stand.id, data=CustomerCreate(first_name="Ada", consent=True)
    )
    session.add(
        Visit(
            workspace_id=stand.id,
            customer_id=customer.id,
            plate_number=3,
            created_at=utcnow() - timedelta(minutes=1),
        )
    )
    session.commit()

    page = client.get(BASE, headers={"X-Customer-Key": customer.key}).json()
    assert page["customer"]["window_seconds"] == SIX_HOURS
    assert page["customer"]["plate_number"] == 3
    r = scan_again(client, customer.key, source="qr")
    assert r.status_code == 409
    assert r.json()["detail"]["seconds_left"] > SIX_HOURS - 120
