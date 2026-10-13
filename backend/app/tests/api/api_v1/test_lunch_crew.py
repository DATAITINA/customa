"""Lunch Crew through the real API: friends share one card; every 6th crew plate's jara goes to
the next member in join order (like ajo). Customers not in a crew count exactly as before.

Uses a normal stand with the default 6-hour window (not the 30-second demo stand).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action, customer_action, user_action, visit_action
from app.core.config import settings
from app.models import CharacterCreate, Crew, CrewMember, CrewPlate, JaraReward, Visit
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting

SIX_HOURS = 6 * 60 * 60
SLUG = "crew-test-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}/crew"
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
        name="Crew Test Stand",
        description="Test stand",
        character=CharacterCreate(name="Pot"),
        slug=SLUG,
    )
    # Outside a request the owner-membership hook does not run (see app/seed/demo.py).
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    session.commit()
    global SCAN
    SCAN = scan_code(workspace, resolve_stand_settings(session, workspace))
    return workspace


@pytest.fixture
def crew_on(session: Session, stand):
    set_stand_setting(session, stand, "LUNCH_CREW_ENABLED", True)
    session.commit()
    return stand


def h(key: str) -> dict[str, str]:
    return {"X-Customer-Key": key}


def sign_up(client: TestClient, name: str) -> str:
    """A new customer: their first plate counts on their own card."""
    r = client.post(f"{BASE}/visits", json={"consent": True, "first_name": name, "scan": SCAN})
    assert r.status_code == 200, r.text
    assert r.json()["crew"] is None
    return r.json()["customer"]["key"]


def wait_6_hours(session: Session, key: str) -> None:
    """Pretend the customer's last plate was counted six hours ago."""
    customer = customer_action.get_by_all(session, key=key)
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = utcnow() - timedelta(seconds=SIX_HOURS)
    session.add(visit)
    session.commit()


def scan(client: TestClient, session: Session, key: str) -> dict:
    wait_6_hours(session, key)
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": SCAN}, headers=h(key))
    assert r.status_code == 200, r.text
    return r.json()


def crew_state(client: TestClient, key: str | None = None, code: str | None = None) -> dict:
    r = client.get(
        f"{BASE}/crew", params={"code": code} if code else None, headers=h(key) if key else None
    )
    assert r.status_code == 200, r.text
    return r.json()


def create(client: TestClient, key: str, name: str = "Office Crew") -> dict:
    r = client.post(f"{BASE}/crew", json={"name": name}, headers=h(key))
    assert r.status_code == 200, r.text
    return r.json()["crew"]


def join(client: TestClient, key: str, code: str):
    return client.post(f"{BASE}/crew/join", json={"code": code}, headers=h(key))


def test_disabled_means_no_crew(client: TestClient, session: Session, stand) -> None:
    ada = sign_up(client, "Ada")
    state = crew_state(client, ada)
    assert state["enabled"] is False and state["crew"] is None and state["invite"] is None
    r = client.post(f"{BASE}/crew", json={"name": "Office Crew"}, headers=h(ada))
    assert r.status_code == 403
    for plate in range(2, 7):
        data = scan(client, session, ada)
        assert data["plate_number"] == plate and data["crew"] is None
    assert data["jara"] is not None
    assert data["customer"]["open_jara"] == [data["jara"]]
    assert data["customer"]["crew_name"] is None
    assert data["customer"]["plate_number"] == 6 and data["customer"]["own_plate_number"] == 0


def test_crew_off_after_creating_counts_on_own_card(
    client: TestClient, session: Session, crew_on
) -> None:
    ada, bayo = sign_up(client, "Ada"), sign_up(client, "Bayo")
    code = create(client, ada)["code"]
    assert join(client, bayo, code).status_code == 200
    set_stand_setting(session, crew_on, "LUNCH_CREW_ENABLED", False)
    session.commit()
    data = scan(client, session, ada)
    assert data["plate_number"] == 2 and data["crew"] is None
    assert crew_state(client, ada)["crew"] is None
    assert session.exec(select(CrewPlate)).all() == []


def test_create_join_full_and_leave(client: TestClient, session: Session, crew_on) -> None:
    set_stand_setting(session, crew_on, "LUNCH_CREW_MAX_MEMBERS", 3)
    session.commit()
    ada, bayo, chidi, dayo = (sign_up(client, n) for n in ("Ada", "Bayo", "Chidi", "Dayo"))

    # Unknown customers cannot create or join.
    assert client.post(f"{BASE}/crew", json={"name": "Crew"}).status_code == 404
    assert client.post(f"{BASE}/crew", json={"name": "x"}, headers=h(ada)).status_code == 422

    crew = create(client, ada)
    code = crew["code"]
    assert 6 <= len(code) <= 8
    assert crew["members"] == [{"name": "Ada", "is_me": True, "is_next": True}]
    assert crew["plate_number"] == 0 and crew["plates_for_jara"] == 6
    assert crew["next_jara_to"] == "Ada" and crew["my_turn_position"] == 1
    r = client.post(f"{BASE}/crew", json={"name": "Second"}, headers=h(ada))
    assert r.status_code == 409

    # Someone opening the invite link sees "Join Office Crew".
    state = crew_state(client, bayo, code=code)
    assert state["crew"] is None
    assert state["invite"]["name"] == "Office Crew"
    assert state["invite"]["members_count"] == 1 and state["invite"]["full"] is False

    assert join(client, bayo, "ZZZZZZ").status_code == 404
    r = join(client, bayo, code.lower())
    assert r.status_code == 200
    assert [m["name"] for m in r.json()["crew"]["members"]] == ["Ada", "Bayo"]
    assert r.json()["crew"]["my_turn_position"] == 2
    assert join(client, bayo, code).status_code == 409
    assert join(client, chidi, code).status_code == 200
    assert crew_state(client, dayo, code=code)["invite"]["full"] is True
    r = join(client, dayo, code)
    assert r.status_code == 409

    r = client.post(f"{BASE}/crew/leave", headers=h(bayo))
    assert r.status_code == 200 and r.json()["crew"] is None
    assert client.post(f"{BASE}/crew/leave", headers=h(bayo)).status_code == 404
    assert join(client, dayo, code).status_code == 200
    names = [m["name"] for m in crew_state(client, ada)["crew"]["members"]]
    assert names == ["Ada", "Chidi", "Dayo"]


def test_crew_plates_rotation_and_open_jara(client: TestClient, session: Session, crew_on) -> None:
    ada, bayo, chidi = (sign_up(client, n) for n in ("Ada", "Bayo", "Chidi"))
    code = create(client, ada)["code"]
    for key in (bayo, chidi):
        assert join(client, key, code).status_code == 200

    # Crew plates count 1..6 whoever scans.
    numbers = []
    for key in (bayo, chidi, bayo, chidi, bayo):
        data = scan(client, session, key)
        numbers.append(data["plate_number"])
        assert data["crew"]["name"] == "Office Crew"
        assert data["crew"]["plate_number"] == data["plate_number"]
        assert data["crew"]["jara_to"] is None and data["jara"] is None
        assert data["customer"]["crew_name"] == "Office Crew"
        assert data["customer"]["plate_number"] == data["plate_number"]
    assert numbers == [1, 2, 3, 4, 5]

    # The 6-hour rule is still per person.
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": SCAN}, headers=h(bayo))
    assert r.status_code == 409
    assert r.json()["detail"]["seconds_left"] > SIX_HOURS - 10
    assert r.json()["detail"]["customer"]["plate_number"] == 5

    # Chidi scans plate 6: it is Ada's turn. Chidi sees who wins, but gets no code.
    data = scan(client, session, chidi)
    assert data["plate_number"] == 6
    assert data["crew"]["jara_to"] == "Ada" and data["crew"]["jara_to_me"] is False
    assert data["jara"] is None
    assert data["customer"]["open_jara"] == []

    # Ada sees her code on her own page.
    page = client.get(BASE, headers=h(ada)).json()
    codes = page["customer"]["open_jara"]
    assert len(codes) == 1 and codes[0]["code"].startswith("JARA-")
    assert page["customer"]["crew_name"] == "Office Crew"
    assert page["customer"]["plate_number"] == 6

    state = crew_state(client, chidi)["crew"]
    assert state["plate_number"] == 0 and state["next_jara_to"] == "Bayo"
    assert state["my_turn_position"] == 2

    # Next rounds: Bayo, then Chidi, then Ada again.
    winners = []
    for _round in range(3):
        for key in (ada, bayo, chidi, ada, bayo, chidi):
            data = scan(client, session, key)
        winners.append(data["crew"]["jara_to"])
        if data["crew"]["jara_to_me"]:
            assert data["jara"] is not None  # Chidi scanned his own turn's plate
    assert winners == ["Bayo", "Chidi", "Ada"]
    # One jara per 6 crew plates.
    assert len(session.exec(select(JaraReward)).all()) == 4


def test_individual_card_resumes_after_leaving(
    client: TestClient, session: Session, crew_on
) -> None:
    ada, bayo, chidi = (sign_up(client, n) for n in ("Ada", "Bayo", "Chidi"))
    assert scan(client, session, ada)["plate_number"] == 2  # own card: 1, 2
    code = create(client, ada)["code"]
    for key in (bayo, chidi):
        join(client, key, code)
    # Her own card is paused at plate 2 while she is in the crew.
    me = client.get(BASE, headers=h(ada)).json()["customer"]
    assert me["crew_name"] == "Office Crew"
    assert me["plate_number"] == 0 and me["own_plate_number"] == 2
    data = scan(client, session, ada)
    assert data["plate_number"] == 1  # crew card
    assert data["customer"]["own_plate_number"] == 2
    assert scan(client, session, bayo)["plate_number"] == 2
    assert client.post(f"{BASE}/crew/leave", headers=h(ada)).status_code == 200

    data = scan(client, session, ada)
    assert data["plate_number"] == 3 and data["crew"] is None
    assert data["customer"]["crew_name"] is None
    page = client.get(BASE, headers=h(ada)).json()
    assert page["customer"]["plate_number"] == 3
    assert page["customer"]["own_plate_number"] == 3
    assert scan(client, session, chidi)["plate_number"] == 3  # crew card goes on


def test_delete_my_data_with_crew(client: TestClient, session: Session, crew_on) -> None:
    ada, bayo, chidi = (sign_up(client, n) for n in ("Ada", "Bayo", "Chidi"))
    code = create(client, bayo)["code"]  # Bayo first in line
    for key in (ada, chidi):
        join(client, key, code)
    for key in (bayo, chidi, ada, chidi, bayo, ada):  # Ada scans plate 6, Bayo wins
        data = scan(client, session, key)
    assert data["crew"]["jara_to"] == "Bayo"
    bayo_code = client.get(BASE, headers=h(bayo)).json()["customer"]["open_jara"][0]["code"]

    r = client.delete(f"{BASE}/me", headers=h(ada))
    assert r.status_code == 200, r.text
    assert customer_action.get_by_all(session, key=ada) is None

    # Bayo keeps his jara; the crew goes on without Ada.
    page = client.get(BASE, headers=h(bayo)).json()
    assert page["customer"]["open_jara"] == [{"code": bayo_code}]
    members = [m["name"] for m in crew_state(client, bayo)["crew"]["members"]]
    assert members == ["Bayo", "Chidi"]
    assert scan(client, session, chidi)["plate_number"] == 1

    # The last members delete their data: the crew is gone, nothing is left behind.
    for key in (bayo, chidi):
        assert client.delete(f"{BASE}/me", headers=h(key)).status_code == 200
    assert session.exec(select(Crew)).all() == []
    assert session.exec(select(CrewMember)).all() == []
    assert session.exec(select(Visit).where(Visit.workspace_id == crew_on.id)).all() == []


def test_vendor_sees_crews_and_switches_feature(
    client: TestClient, session: Session, stand, superuser_account_token_headers
) -> None:
    headers = superuser_account_token_headers
    r = client.get(VENDOR, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False and r.json()["crews"] == []
    assert client.get(VENDOR).status_code in (401, 403)

    r = client.put(f"{VENDOR}/settings", json={"enabled": True}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True

    ada, bayo = sign_up(client, "Ada"), sign_up(client, "Bayo")
    code = create(client, ada)["code"]
    join(client, bayo, code)
    scan(client, session, bayo)
    crews = client.get(VENDOR, headers=headers).json()["crews"]
    assert crews == [
        {
            "name": "Office Crew",
            "members": ["Ada", "Bayo"],
            "plate_number": 1,
            "plates_for_jara": 6,
            "next_jara_to": "Ada",
        }
    ]

    r = client.put(f"{VENDOR}/settings", json={"enabled": False}, headers=headers)
    assert r.json()["enabled"] is False
    assert crew_state(client, ada)["enabled"] is False
