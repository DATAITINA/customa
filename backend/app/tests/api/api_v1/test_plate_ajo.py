"""Plate Ajo through the real API: prepay plates at today's price, then use one per visit.

The money goes from the customer to the vendor's own account by transfer; Customa only keeps
the count, so these tests check the count, the locked price and who may do what.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, character_action, customer_action, user_action
from app.core.config import settings
from app.models import CharacterCreate, PlateBundle, PlateUse, Visit
from app.services.stands import create_stand, set_stand_setting

SLUG = "ajo-pot-test"
PUBLIC = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
MENU = [
    {"item": "Afang and garri", "price": 2000},
    {"item": "Jollof rice", "price": 1500},
]
BANK = {"bank_name": "Opay", "account_number": "8031234567", "account_name": "Mama Afang"}
SIX_HOURS = 6 * 60 * 60


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Ajo Pot Test",
        description="Test stand",
        character=CharacterCreate(name="Pot", menu=MENU),
        slug=SLUG,
    )
    # Outside a request the owner-membership hook does not fire (see app/seed/demo.py).
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    session.commit()
    return workspace


@pytest.fixture
def ajo_on(session: Session, stand):
    for key, value in (
        ("PLATE_AJO_ENABLED", True),
        ("AJO_BANK_NAME", BANK["bank_name"]),
        ("AJO_ACCOUNT_NUMBER", BANK["account_number"]),
        ("AJO_ACCOUNT_NAME", BANK["account_name"]),
    ):
        set_stand_setting(session, stand, key, value)
    session.commit()
    return stand


def new_customer(client: TestClient, name: str = "Ada") -> dict[str, str]:
    r = client.post(f"{PUBLIC}/visits", json={"consent": True, "first_name": name})
    assert r.status_code == 200, r.text
    return {"X-Customer-Key": r.json()["customer"]["key"]}


def buy(client: TestClient, who: dict, item="Afang and garri", plates=5, payer="Ada Okon", **extra):
    return client.post(
        f"{PUBLIC}/ajo/bundles",
        json={"item": item, "plates": plates, "payer_name": payer, **extra},
        headers=who,
    )


def use(client: TestClient, who: dict):
    return client.post(f"{PUBLIC}/ajo/use", headers=who)


def last_use_back(session: Session, seconds: int) -> None:
    """Pretend the latest prepaid plate was used `seconds` ago."""
    row = session.exec(select(PlateUse).order_by(PlateUse.id.desc())).first()
    row.created_at = utcnow() - timedelta(seconds=seconds)
    session.add(row)
    session.commit()


def last_visit_back(session: Session, who: dict, seconds: int) -> None:
    customer = customer_action.get_by_all(session, key=who["X-Customer-Key"])
    visit = session.exec(
        select(Visit).where(Visit.customer_id == customer.id).order_by(Visit.id.desc())
    ).first()
    visit.created_at = utcnow() - timedelta(seconds=seconds)
    session.add(visit)
    session.commit()


def test_hidden_until_vendor_turns_it_on_with_bank_details(
    client: TestClient, session: Session, stand, superuser_account_token_headers
) -> None:
    vendor = superuser_account_token_headers
    page = client.get(f"{PUBLIC}/ajo").json()
    assert page["available"] is False
    assert page["bank"] is None
    assert page["items"] == []

    # Cannot switch on without all three details.
    r = client.put(f"{VENDOR}/ajo/settings", json={"enabled": True}, headers=vendor)
    assert r.status_code == 400
    assert "account number" in r.json()["detail"]
    r = client.put(
        f"{VENDOR}/ajo/settings",
        json={"enabled": True, **BANK, "account_number": "12345"},
        headers=vendor,
    )
    assert r.status_code == 400
    assert "10 digits" in r.json()["detail"]

    r = client.put(f"{VENDOR}/ajo/settings", json={"enabled": True, **BANK}, headers=vendor)
    assert r.status_code == 200, r.text
    assert r.json()["available"] is True

    page = client.get(f"{PUBLIC}/ajo").json()
    assert page["available"] is True
    assert page["bank"] == BANK
    assert page["items"] == MENU
    assert page["bundle_sizes"] == [5, 10]
    assert page["bundles"] == []

    # Turning it off hides it again but keeps the saved details.
    r = client.put(f"{VENDOR}/ajo/settings", json={"enabled": False}, headers=vendor)
    assert r.status_code == 200
    assert r.json()["account_number"] == BANK["account_number"]
    assert client.get(f"{PUBLIC}/ajo").json()["available"] is False


def test_vendor_routes_need_a_member(client: TestClient, ajo_on) -> None:
    assert client.get(f"{VENDOR}/ajo").status_code in (401, 403)
    r = client.put(f"{VENDOR}/ajo/settings", json={"enabled": False})
    assert r.status_code in (401, 403)


def test_price_comes_from_the_menu_and_one_pending_at_a_time(
    client: TestClient, session: Session, ajo_on
) -> None:
    assert buy(client, {"X-Customer-Key": "nobody"}).status_code == 404

    ada = new_customer(client)
    assert buy(client, ada, item="Suya").status_code == 400
    assert buy(client, ada, plates=7).status_code == 400
    assert buy(client, ada, payer="A").status_code == 400

    r = buy(client, ada, item="afang and garri", unit_price=1, price=1)
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["item"] == "Afang and garri"
    assert bundle["unit_price"] == 2000
    assert bundle["status"] == "pending"
    assert bundle["plates_left"] == 5

    r = buy(client, ada, item="Jollof rice", plates=10)
    assert r.status_code == 409

    page = client.get(f"{PUBLIC}/ajo", headers=ada).json()
    assert [b["status"] for b in page["bundles"]] == ["pending"]
    # Using a plate before the vendor confirms is refused.
    assert use(client, ada).status_code == 409


def test_confirm_use_and_stamp(
    client: TestClient, session: Session, ajo_on, superuser_account_token_headers
) -> None:
    vendor = superuser_account_token_headers
    ada = new_customer(client)
    bundle_id = buy(client, ada).json()["bundle"]["id"]

    dash = client.get(f"{VENDOR}/ajo", headers=vendor).json()
    assert dash["pending"][0]["id"] == bundle_id
    assert dash["pending"][0]["name"] == "Ada"
    assert dash["pending"][0]["payer_name"] == "Ada Okon"
    assert dash["pending"][0]["total"] == 10000

    r = client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=vendor)
    assert r.status_code == 200, r.text
    assert r.json()["bundle"]["status"] == "active"
    assert (
        client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=vendor).status_code == 409
    )

    # The vendor raises the menu price later: the bundle keeps its locked price.
    character_action.update(
        session,
        model=character_action.get_for_stand(session, workspace_id=ajo_on.id),
        update={"menu": [{"item": "Afang and garri", "price": 2500}]},
    )

    # First prepaid plate: the sign-up plate was just counted, so no stamp (6-hour rule).
    r = use(client, ada)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["bundle"]["plates_left"] == 4
    assert data["bundle"]["unit_price"] == 2000
    assert data["use"]["plate_number"] == 1
    assert data["use"]["plates_total"] == 5
    assert data["use"]["item"] == "Afang and garri"
    assert data["stamp"] == {"counted": False, "plate_number": None, "jara": None}

    # Double tap protection: a second use within 60 seconds is refused and nothing changes.
    r = use(client, ada)
    assert r.status_code == 409
    assert (
        session.exec(select(PlateBundle).where(PlateBundle.id == bundle_id)).one().plates_used == 1
    )

    # A visit later (6 hours on): the prepaid plate also counts a stamp.
    last_use_back(session, 61)
    last_visit_back(session, ada, SIX_HOURS)
    r = use(client, ada)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["use"]["plate_number"] == 2
    assert data["stamp"]["counted"] is True
    assert data["stamp"]["plate_number"] == 2

    dash = client.get(f"{VENDOR}/ajo", headers=vendor).json()
    assert dash["pending"] == []
    assert dash["active"][0]["plates_left"] == 3
    assert [s["plate_number"] for s in dash["served_today"]] == [2, 1]
    assert dash["served_today"][0]["name"] == "Ada"


def test_bundle_finishes_after_last_plate(
    client: TestClient, session: Session, ajo_on, superuser_account_token_headers
) -> None:
    ada = new_customer(client)
    bundle_id = buy(client, ada).json()["bundle"]["id"]
    client.post(
        f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=superuser_account_token_headers
    )
    for plate in range(1, 6):
        r = use(client, ada)
        assert r.status_code == 200, r.text
        assert r.json()["use"]["plate_number"] == plate
        last_use_back(session, 61)
    assert r.json()["bundle"]["status"] == "finished"
    assert r.json()["bundle"]["plates_left"] == 0
    assert use(client, ada).status_code == 409


def test_reject_and_other_stands_bundles(
    client: TestClient, session: Session, ajo_on, superuser_account_token_headers
) -> None:
    vendor = superuser_account_token_headers
    ada = new_customer(client)
    bundle_id = buy(client, ada).json()["bundle"]["id"]
    r = client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/reject", headers=vendor)
    assert r.status_code == 200
    assert r.json()["bundle"]["status"] == "rejected"
    assert (
        client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=vendor).status_code == 409
    )
    assert client.post(f"{VENDOR}/ajo/bundles/999999/confirm", headers=vendor).status_code == 404

    # After a rejection the customer can start again.
    assert buy(client, ada).status_code == 200


def test_delete_my_data_refused_while_plates_remain(
    client: TestClient, session: Session, ajo_on, superuser_account_token_headers
) -> None:
    vendor = superuser_account_token_headers
    ada = new_customer(client)
    bundle_id = buy(client, ada).json()["bundle"]["id"]

    r = client.delete(f"{PUBLIC}/me", headers=ada)
    assert r.status_code == 409
    assert "prepaid plates" in r.json()["detail"]

    client.post(f"{VENDOR}/ajo/bundles/{bundle_id}/confirm", headers=vendor)
    assert client.delete(f"{PUBLIC}/me", headers=ada).status_code == 409
    assert customer_action.get_by_all(session, key=ada["X-Customer-Key"]) is not None

    # Plates used up: the data can go, Ajo rows included.
    for _ in range(5):
        assert use(client, ada).status_code == 200
        last_use_back(session, 61)
    r = client.delete(f"{PUBLIC}/me", headers=ada)
    assert r.status_code == 200, r.text
    assert session.exec(select(PlateBundle).where(PlateBundle.id == bundle_id)).first() is None
    assert session.exec(select(PlateUse).where(PlateUse.bundle_id == bundle_id)).first() is None
