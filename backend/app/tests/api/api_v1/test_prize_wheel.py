"""Prize Wheel through the real API: the vendor's wheel, the customer's spin on plate 6, and the
vendor's code check and redemption."""

import base64
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, customer_action, user_action, visit_action
from app.core.config import settings
from app.models import CharacterCreate, JaraPrize, JaraReward, WheelItem
from app.services import prize_wheel
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings

SLUG = "wheel-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
AUTH = {"Authorization": "Bearer *"}
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 300).decode()
SIX_HOURS = 6 * 60 * 60 + 5


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session, owner=owner, name="Mama Afang", description="Test stand",
        character=CharacterCreate(name="Afangy Pot", body="pot", color="okra", accessory="chef"), slug=SLUG,
    )
    user_action.create_membership(session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id)
    session.commit()
    return workspace


def add(client: TestClient, name: str, **body) -> dict:
    r = client.post(f"{VENDOR}/wheel/items", json={"name": name, **body}, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def publish(client: TestClient, enabled: bool = True):
    return client.put(f"{VENDOR}/wheel", json={"enabled": enabled}, headers=AUTH)


def live_wheel(client: TestClient) -> dict:
    add(client, "Jollof rice", prize="A free plate of jollof", weight=1, photo=JPEG)
    add(client, "Puff-puff", prize="5 puff-puff", weight=5)
    add(client, "Zobo", prize="A cold zobo", weight=3)
    r = publish(client)
    assert r.status_code == 200, r.text
    return r.json()


def to_plate_6(client: TestClient, session: Session, stand) -> tuple[dict, dict]:
    """A customer with six plates: returns their headers and the plate-6 response."""
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    r = client.post(f"{BASE}/visits", json={"consent": True, "first_name": "Ada", "scan": scan})
    key = r.json()["customer"]["key"]
    headers = {"X-Customer-Key": key}
    for _ in range(5):
        customer = customer_action.get_by_all(session, key=key)
        visit = visit_action.last_for_customer(session, customer_id=customer.id)
        visit.created_at = utcnow() - timedelta(seconds=SIX_HOURS)
        session.add(visit)
        session.commit()
        r = client.post(f"{BASE}/visits", json={"consent": True, "scan": scan}, headers=headers)
        assert r.status_code == 200, r.text
    assert r.json()["plate_number"] == 6
    return headers, r.json()


def test_vendor_builds_and_publishes_a_wheel(client: TestClient, stand) -> None:
    assert client.get(BASE).json()["features"]["prize_wheel"] is False
    add(client, "Jollof rice", prize="A free plate", photo=JPEG)
    # One prize is not a wheel yet.
    r = publish(client)
    assert r.status_code == 409 and "at least 2" in r.json()["detail"]
    view = add(client, "Zobo", weight=5)
    assert [i["name"] for i in view["items"]] == ["Jollof rice", "Zobo"]
    assert view["items"][0]["photo"].startswith(f"/public/{SLUG}/wheel/items/")
    assert publish(client).json()["enabled"] is True
    assert client.get(BASE).json()["features"]["prize_wheel"] is True

    # The photo is served with long caching.
    photo = client.get(f"{settings.API_V1_STR}{view['items'][0]['photo']}")
    assert photo.status_code == 200 and "immutable" in photo.headers["cache-control"]

    # Up to six prizes.
    for n in range(4):
        add(client, f"Prize {n}")
    r = client.post(f"{VENDOR}/wheel/items", json={"name": "Seventh"}, headers=AUTH)
    assert r.status_code == 409

    # Bad input is refused.
    item_id = view["items"][0]["id"]
    assert client.put(f"{VENDOR}/wheel/items/{item_id}", json={"weight": 2}, headers=AUTH).status_code == 422
    assert client.put(f"{VENDOR}/wheel/items/{item_id}", json={"photo": "data:text/plain;base64,aGk="}, headers=AUTH).status_code == 400
    # Customers and other people cannot change the wheel.
    assert client.post(f"{VENDOR}/wheel/items", json={"name": "Hack"}).status_code == 401


def test_too_few_prizes_pauses_the_wheel(client: TestClient, stand) -> None:
    view = live_wheel(client)
    ids = [i["id"] for i in view["items"]]
    client.put(f"{VENDOR}/wheel/items/{ids[0]}", json={"available": False}, headers=AUTH)
    assert client.get(f"{VENDOR}/wheel", headers=AUTH).json()["enabled"] is True  # 2 left
    client.delete(f"{VENDOR}/wheel/items/{ids[1]}", headers=AUTH)
    assert client.get(f"{VENDOR}/wheel", headers=AUTH).json()["enabled"] is False


def test_plate_6_spin_code_and_redeem_once(client: TestClient, session: Session, stand) -> None:
    live_wheel(client)
    headers, plate6 = to_plate_6(client, session, stand)
    # The jara is a spin: no code yet.
    assert plate6["jara"]["code"] is None and plate6["jara"]["spin"]
    jara_id = plate6["jara"]["spin"]
    card = client.get(BASE, headers=headers).json()["customer"]["open_jara"]
    assert card == [{"code": None, "spin": jara_id}]
    state = client.get(f"{BASE}/wheel", headers=headers).json()
    assert state["enabled"] and state["spins"] == [jara_id] and len(state["items"]) == 3
    assert "available" not in state["items"][0]

    # The vendor sees a jara waiting for its spin.
    dash = client.get(f"{VENDOR}/dashboard", headers=AUTH).json()
    assert dash["open_jara"][0]["spin_pending"] is True
    old_code = dash["open_jara"][0]["code"]
    assert client.get(f"{VENDOR}/jara/{old_code}", headers=AUTH).json()["status"] == "not_spun"

    r = client.post(f"{BASE}/wheel/spin", json={"jara_id": jara_id}, headers=headers)
    assert r.status_code == 200, r.text
    spin = r.json()
    names = [s["name"] for s in spin["wheel"]]
    assert spin["wheel"][spin["slot"]]["name"] == spin["prize"]["name"] and set(names) == {"Jollof rice", "Puff-puff", "Zobo"}
    assert 0.2 <= spin["landing"] <= 0.8
    code = spin["prize"]["code"]
    assert code != old_code and len(code) == len("JARA-XXXX-XXXX")

    # Spinning again (a reload, a double tap) gives the same result.
    again = client.post(f"{BASE}/wheel/spin", json={"jara_id": jara_id}, headers=headers).json()
    assert again == spin
    assert len(client.get(f"{BASE}/wheel", headers=headers).json()["won"]) == 1
    assert client.get(BASE, headers=headers).json()["customer"]["open_jara"][0]["prize"] == spin["prize"]["name"]

    # The vendor checks the code, typed sloppily or scanned.
    check = client.get(f"{VENDOR}/jara/{code.lower().replace('-', ' ')}", headers=AUTH).json()
    assert check["status"] == "valid" and check["customer"] == "Ada"
    assert check["prize"]["name"] == spin["prize"]["name"]
    assert client.get(f"{VENDOR}/jara/{old_code}", headers=AUTH).json()["status"] == "unknown"

    r = client.post(f"{VENDOR}/jara/{code}/redeem", headers=AUTH)
    assert r.status_code == 200 and r.json()["prize"] == spin["prize"]["name"]
    # Once only: a screenshot of the used code is worth nothing.
    assert client.post(f"{VENDOR}/jara/{code}/redeem", headers=AUTH).status_code == 409
    check = client.get(f"{VENDOR}/jara/{code}", headers=AUTH).json()
    assert check["status"] == "redeemed" and check["prize"]["redeemed_at"]
    assert client.get(f"{VENDOR}/wheel", headers=AUTH).json()["stats"] == {"spins": 1, "given": 1}
    # A used jara cannot spin again: the same result comes back, now marked given.
    after = client.post(f"{BASE}/wheel/spin", json={"jara_id": jara_id}, headers=headers).json()
    assert after["prize"]["redeemed"] is True and after["slot"] == spin["slot"] and after["prize"]["code"] == code
    assert client.get(f"{BASE}/wheel", headers=headers).json()["won"] == []


def test_spins_belong_to_their_customer(client: TestClient, session: Session, stand) -> None:
    live_wheel(client)
    _, plate6 = to_plate_6(client, session, stand)
    jara_id = plate6["jara"]["spin"]
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    other = client.post(f"{BASE}/visits", json={"consent": True, "scan": scan}).json()["customer"]["key"]
    r = client.post(f"{BASE}/wheel/spin", json={"jara_id": jara_id}, headers={"X-Customer-Key": other})
    assert r.status_code == 404
    assert client.post(f"{BASE}/wheel/spin", json={"jara_id": jara_id}).status_code == 404


def test_expired_and_other_stand_codes(client: TestClient, session: Session, stand) -> None:
    live_wheel(client)
    headers, plate6 = to_plate_6(client, session, stand)
    spin = client.post(f"{BASE}/wheel/spin", json={"jara_id": plate6["jara"]["spin"]}, headers=headers).json()
    prize = session.exec(select(JaraPrize)).one()
    prize.expires_at = utcnow() - timedelta(minutes=1)
    session.add(prize)
    session.commit()
    code = spin["prize"]["code"]
    assert client.get(f"{VENDOR}/jara/{code}", headers=AUTH).json()["status"] == "expired"
    r = client.post(f"{VENDOR}/jara/{code}/redeem", headers=AUTH)
    assert r.status_code == 409 and "expired" in r.json()["detail"]

    # A code from another stand.
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    other, _ = create_stand(session, owner=owner, name="Other", description="x", character=CharacterCreate(name="Bo"), slug="other-stand")
    user_action.create_membership(session, account_id=owner.id, workspace_id=other.id, owner_id=owner.id)
    session.commit()
    r = client.get(f"{settings.API_V1_STR}/stands/other-stand/jara/{code}", headers=AUTH)
    assert r.json()["status"] == "other_stand"
    assert client.get(f"{VENDOR}/jara/JARA-ZZZZ-ZZZZ", headers=AUTH).json()["status"] == "unknown"


def test_wheel_off_keeps_the_plain_jara(client: TestClient, session: Session, stand) -> None:
    headers, plate6 = to_plate_6(client, session, stand)
    assert plate6["jara"] == {"code": plate6["jara"]["code"]} and plate6["jara"]["code"].startswith("JARA-")
    r = client.post(f"{BASE}/wheel/spin", json={"jara_id": session.exec(select(JaraReward.id)).first()}, headers=headers)
    assert r.status_code == 409
    assert client.post(f"{VENDOR}/jara/{plate6['jara']['code']}/redeem", headers=AUTH).status_code == 200


def test_weights_shape_the_odds(session: Session, stand) -> None:
    """Often (5) comes up about five times as much as rarely (1)."""
    for name, weight in (("Rare", 1), ("Often", 5)):
        session.add(WheelItem(workspace_id=stand.id, name=name, weight=weight))
    session.commit()
    picks = Counter(
        prize_wheel._rng.choices(["Rare", "Often"], weights=[1, 5])[0] for _ in range(6000)
    )
    assert 3.5 < picks["Often"] / picks["Rare"] < 7


def test_delete_my_data_removes_spins(client: TestClient, session: Session, stand) -> None:
    live_wheel(client)
    headers, plate6 = to_plate_6(client, session, stand)
    client.post(f"{BASE}/wheel/spin", json={"jara_id": plate6["jara"]["spin"]}, headers=headers)
    assert client.delete(f"{BASE}/me", headers=headers).status_code == 200
    session.expire_all()
    assert session.exec(select(JaraPrize)).all() == []
