"""Pot Alert through the real API: customers watch dishes, the vendor says "ready now"."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, PotReady, PotWatch
from app.services.stands import create_stand, set_stand_setting

SLUG = "afang-pot-test"
PUBLIC = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
MENU = [
    {"item": "Afang soup", "price": 2000},
    {"item": "Pepper soup", "price": 1500},
    {"item": "Jollof rice", "price": 1200},
]


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Afang Pot Test",
        description="Test stand",
        character=CharacterCreate(name="Pot", menu=MENU),
        slug=SLUG,
    )
    # Outside a request the owner-membership hook does not fire (see app/seed/demo.py).
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    set_stand_setting(session, workspace, "POT_ALERT_ENABLED", True)
    session.commit()
    return workspace


def new_customer(client: TestClient, name: str = "Ada") -> str:
    r = client.post(f"{PUBLIC}/visits", json={"consent": True, "first_name": name})
    assert r.status_code == 200, r.text
    return r.json()["customer"]["key"]


def watch(
    client: TestClient, key: str, items: list[str], phone: str = "0803 123 4567", consent=True
):
    body = {"items": items, "phone": phone}
    if consent is not None:
        body["consent"] = consent
    return client.put(f"{PUBLIC}/pot/watches", json=body, headers={"X-Customer-Key": key})


def test_off_hides_everything(client: TestClient, session: Session, stand) -> None:
    set_stand_setting(session, stand, "POT_ALERT_ENABLED", False)
    session.commit()
    key = new_customer(client)
    r = client.get(f"{PUBLIC}/pot", headers={"X-Customer-Key": key})
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "items": [], "ready": [], "my": None}
    assert watch(client, key, ["Afang soup"]).status_code == 404


def test_customer_watches_and_sees_masked_phone(
    client: TestClient, session: Session, stand
) -> None:
    key = new_customer(client)
    r = watch(client, key, ["afang soup", "Pepper soup"], phone="+234 803-123-4567")
    assert r.status_code == 200, r.text
    assert r.json()["my"] == {"items": ["Afang soup", "Pepper soup"], "phone_masked": "•••• 4567"}

    page = client.get(f"{PUBLIC}/pot", headers={"X-Customer-Key": key}).json()
    assert page["enabled"] is True
    assert page["items"] == ["Afang soup", "Pepper soup", "Jollof rice"]
    assert page["my"]["items"] == ["Afang soup", "Pepper soup"]
    assert "8031234567" not in str(page)

    rows = session.exec(select(PotWatch).where(PotWatch.workspace_id == stand.id)).all()
    assert {w.phone for w in rows} == {"2348031234567"}

    # Changing the list replaces it.
    assert watch(client, key, ["Jollof rice"]).json()["my"]["items"] == ["Jollof rice"]
    # Stop alerts.
    r = client.delete(f"{PUBLIC}/pot/watches", headers={"X-Customer-Key": key})
    assert r.status_code == 200
    assert client.get(f"{PUBLIC}/pot", headers={"X-Customer-Key": key}).json()["my"] is None


def test_customer_bad_input(client: TestClient, stand) -> None:
    key = new_customer(client)
    assert watch(client, key, ["Afang soup"], phone="12345").status_code == 400
    assert watch(client, key, ["Afang soup"], phone="0103 123 4567").status_code == 400
    r = watch(client, key, ["Egusi"])
    assert r.status_code == 400
    assert "menu" in r.json()["detail"]
    assert watch(client, key, []).status_code == 400
    # Unknown customer.
    assert watch(client, "not-a-key", ["Afang soup"]).status_code == 404


def test_whatsapp_agreement_required(client: TestClient, session: Session, stand) -> None:
    key = new_customer(client)
    for consent in (None, False):
        r = watch(client, key, ["Afang soup"], consent=consent)
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "Please agree to WhatsApp messages from the vendor"
    assert session.exec(select(PotWatch).where(PotWatch.workspace_id == stand.id)).all() == []
    assert watch(client, key, ["Afang soup"], consent=True).status_code == 200
    # Changing the list asks again; a refused change keeps the saved list.
    assert watch(client, key, ["Pepper soup"], phone="", consent=False).status_code == 400
    my = client.get(f"{PUBLIC}/pot", headers={"X-Customer-Key": key}).json()["my"]
    assert my["items"] == ["Afang soup"]


def test_vendor_ready_flow(
    client: TestClient, session: Session, stand, superuser_account_token_headers
) -> None:
    h = superuser_account_token_headers
    ada = new_customer(client, "Ada")
    tunde = new_customer(client, "Tunde")
    assert watch(client, ada, ["Afang soup"], phone="08031234567").status_code == 200
    assert (
        watch(client, tunde, ["Afang soup", "Pepper soup"], phone="0902 222 3333").status_code
        == 200
    )

    d = client.get(f"{VENDOR}/pot", headers=h)
    assert d.status_code == 200, d.text
    assert d.json()["enabled"] is True
    assert d.json()["demand"] == [
        {"item": "Afang soup", "waiting": 2},
        {"item": "Pepper soup", "waiting": 1},
        {"item": "Jollof rice", "waiting": 0},
    ]

    r = client.post(f"{VENDOR}/pot/ready", json={"item": "Afang soup", "plates_left": 8}, headers=h)
    assert r.status_code == 200, r.text
    ready = r.json()["ready"]
    assert ready["item"] == "Afang soup" and ready["plates_left"] == 8
    assert r.json()["watchers"] == [
        {"name": "Ada", "phone": "2348031234567"},
        {"name": "Tunde", "phone": "2349022223333"},
    ]

    # Everyone sees the banner, nobody sees phones.
    page = client.get(f"{PUBLIC}/pot").json()
    assert [x["item"] for x in page["ready"]] == ["Afang soup"]
    assert "phone" not in str(page["ready"])

    again = client.get(f"{VENDOR}/pot/ready/{ready['id']}/watchers", headers=h)
    assert again.status_code == 200
    assert len(again.json()["watchers"]) == 2

    assert client.post(f"{VENDOR}/pot/ready/{ready['id']}/end", headers=h).status_code == 200
    assert client.get(f"{PUBLIC}/pot").json()["ready"] == []

    # Not on the menu.
    bad = client.post(f"{VENDOR}/pot/ready", json={"item": "Egusi"}, headers=h)
    assert bad.status_code == 400


def test_ready_expires_after_3_hours(
    client: TestClient, session: Session, stand, superuser_account_token_headers
) -> None:
    h = superuser_account_token_headers
    r = client.post(f"{VENDOR}/pot/ready", json={"item": "Pepper soup"}, headers=h)
    assert r.status_code == 200, r.text
    row = session.exec(select(PotReady).where(PotReady.id == r.json()["ready"]["id"])).one()
    row.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3, minutes=1)
    session.add(row)
    session.commit()
    assert client.get(f"{PUBLIC}/pot").json()["ready"] == []


def test_vendor_switch_and_auth(client: TestClient, stand, superuser_account_token_headers) -> None:
    h = superuser_account_token_headers
    r = client.put(f"{VENDOR}/pot/settings", json={"enabled": False}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False
    assert client.get(f"{PUBLIC}/pot").json()["enabled"] is False
    # Without a login the vendor routes are closed.
    assert client.get(f"{VENDOR}/pot").status_code in (401, 403)


def test_delete_my_data_removes_watches(client: TestClient, session: Session, stand) -> None:
    key = new_customer(client)
    assert watch(client, key, ["Afang soup"]).status_code == 200
    r = client.delete(f"{PUBLIC}/me", headers={"X-Customer-Key": key})
    assert r.status_code == 200, r.text
    session.expire_all()
    assert session.exec(select(PotWatch).where(PotWatch.workspace_id == stand.id)).all() == []
