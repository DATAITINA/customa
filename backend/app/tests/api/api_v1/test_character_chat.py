"""Chatting with the stand character through the real API, and the customer delights.

- Private: the vendor's dashboard shows food questions only.
- One short chat per counted plate, closed with a warm cliffhanger, picked up next plate.
- Memory the customer can see and clear; deleted with their data.
- Surprise jara and today's special (vendor settings).

The AI is switched off in these tests, so replies come from the no-AI fallback.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.eventbus as customa_events
from app.actions import account_action, customer_action, user_action, visit_action
from app.api.api_v1.endpoints import public
from app.core.config import settings
from app.models import CharacterCreate, ChatMemory
from app.services import bisi
from app.services.character_chat import JOKES, is_food_question
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings, set_stand_setting

SIX_HOURS = 6 * 60 * 60
SLUG = "chat-test-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
SCAN = ""  # the stand's QR scan code, set by the stand fixture
MENU = [{"item": "Jollof rice", "price": 1500}, {"item": "Afang and fufu", "price": 2500}]


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setattr(bisi, "_ai_configured", lambda: False)


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Chat Test Stand",
        description="Test stand",
        character=CharacterCreate(name="Bisi Pepper", greeting="Welcome o!", menu=MENU),
        slug=SLUG,
    )
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    session.commit()
    global SCAN
    SCAN = scan_code(workspace, resolve_stand_settings(session, workspace))
    return workspace


def h(key: str) -> dict[str, str]:
    return {"X-Customer-Key": key}


def sign_up(client: TestClient, name: str = "Bassey") -> str:
    r = client.post(f"{BASE}/visits", json={"consent": True, "first_name": name, "scan": SCAN})
    assert r.status_code == 200, r.text
    return r.json()["customer"]["key"]


def next_plate(client: TestClient, session: Session, key: str) -> dict:
    """Six hours later, the next plate counts."""
    customer = customer_action.get_by_all(session, key=key)
    visit = visit_action.last_for_customer(session, customer_id=customer.id)
    visit.created_at = utcnow() - timedelta(seconds=SIX_HOURS)
    session.add(visit)
    session.commit()
    r = client.post(f"{BASE}/visits", json={"consent": True, "scan": SCAN}, headers=h(key))
    assert r.status_code == 200, r.text
    return r.json()


def say(client: TestClient, key: str, message: str) -> dict:
    r = client.post(f"{BASE}/chat", json={"message": message, "history": []}, headers=h(key))
    assert r.status_code == 200, r.text
    return r.json()


# --- One short chat per plate -------------------------------------------------------------


def test_chat_needs_a_counted_plate(client: TestClient, stand) -> None:
    assert client.get(f"{BASE}/chat").status_code == 403
    assert client.post(f"{BASE}/chat", json={"message": "hi"}).status_code == 403


def test_chat_opens_with_a_greeting(client: TestClient, stand) -> None:
    key = sign_up(client)
    r = client.get(f"{BASE}/chat", headers=h(key))
    assert r.status_code == 200, r.text
    chat = r.json()
    assert chat["open"] is True
    assert chat["messages_left"] == 8
    assert chat["opener"].startswith("Bassey! Welcome o!")


def test_chat_closes_with_a_cliffhanger_then_reopens_next_plate(
    client: TestClient, session: Session, stand, monkeypatch
) -> None:
    set_stand_setting(session, stand, "CHAT_MESSAGES_PER_PLATE", 3)
    session.commit()
    key = sign_up(client)

    real_reply = public.chat_reply

    def reply_with_follow_up(**kwargs):
        reply, source, _ = real_reply(**kwargs)
        return reply, source, ("How did the interview go?" if kwargs["ctx"].closing else None)

    monkeypatch.setattr(public, "chat_reply", reply_with_follow_up)

    assert say(client, key, "Hello!")["chat"]["messages_left"] == 2
    assert say(client, key, "I get interview tomorrow")["chat"]["messages_left"] == 1
    last = say(client, key, "I have to go")
    assert "Come back for your next plate" in last["reply"]
    assert last["chat"]["open"] is False
    assert last["chat"]["memory"]["follow_up"] == "How did the interview go?"

    # Closed until the next plate: no reply, nothing used.
    closed = say(client, key, "One more thing")
    assert closed["reply"] is None and closed["chat"]["open"] is False
    assert closed["chat"]["seconds_left"] > 0

    # Next plate: the chat opens again and picks up where it stopped, once.
    next_plate(client, session, key)
    chat = client.get(f"{BASE}/chat", headers=h(key)).json()
    assert chat["open"] is True and chat["messages_left"] == 3
    assert "How did the interview go?" in chat["opener"]
    assert chat["memory"]["follow_up"] is None
    # A page reload shows the same opener and does not reset the count.
    say(client, key, "It went well!")
    again = client.get(f"{BASE}/chat", headers=h(key)).json()
    assert again["opener"] == chat["opener"] and again["messages_left"] == 2


def test_almost_there_and_todays_special_in_the_opener(
    client: TestClient, session: Session, stand
) -> None:
    key = sign_up(client)
    for _ in range(4):
        next_plate(client, session, key)  # plates 2..5
    opener = client.get(f"{BASE}/chat", headers=h(key)).json()["opener"]
    assert "ONE more plate" in opener

    vendor = {"Authorization": "Bearer *"}
    r = client.put(f"{VENDOR}/delights/special", json={"text": "Peppered snail"}, headers=vendor)
    assert r.status_code == 200, r.text
    assert r.json()["special"] == "Peppered snail"
    next_plate(client, session, key)  # plate 6
    chat = client.get(f"{BASE}/chat", headers=h(key)).json()
    assert chat["special"] == "Peppered snail"
    assert "Today's special: Peppered snail" in chat["opener"]
    assert "Peppered snail" in say(client, key, "Any special today?")["reply"]

    assert client.put(f"{VENDOR}/delights/special", json={"text": ""}, headers=vendor).json()["special"] is None


def test_joke_and_recommendation(client: TestClient, stand) -> None:
    key = sign_up(client)
    assert say(client, key, "Tell me a joke")["reply"] in JOKES
    reply = say(client, key, "What should I eat today?")["reply"]
    assert any(m["item"] in reply for m in MENU)


# --- Privacy and memory ------------------------------------------------------------------


def test_vendor_sees_food_questions_only(client: TestClient, stand) -> None:
    key = sign_up(client)
    say(client, key, "My exam was so hard today, I feel tired")
    say(client, key, "How much is the jollof rice?")
    say(client, key, "Do you have afang today?")
    say(client, key, "What do you think about my boyfriend?")
    r = client.get(f"{VENDOR}/dashboard", headers={"Authorization": "Bearer *"})
    assert r.status_code == 200, r.text
    questions = [q["question"] for q in r.json()["recent_questions"]]
    assert sorted(questions) == ["Do you have afang today?", "How much is the jollof rice?"]


def test_memory_can_be_seen_and_cleared(client: TestClient, session: Session, stand) -> None:
    key = sign_up(client)
    memory = say(client, key, "I really love your jollof rice")["chat"]["memory"]
    assert memory["favourite_item"] == "Jollof rice"
    assert memory["last_item"] == "Jollof rice"

    r = client.delete(f"{BASE}/chat/memory", headers=h(key))
    assert r.status_code == 200
    assert r.json()["memory"] == {"favourite_item": None, "last_item": None, "follow_up": None}


def test_delete_my_data_removes_chat_memory(client: TestClient, session: Session, stand) -> None:
    key = sign_up(client)
    say(client, key, "I love the afang and fufu")
    customer_id = customer_action.get_by_all(session, key=key).id
    assert client.delete(f"{BASE}/me", headers=h(key)).status_code == 200
    session.expire_all()
    assert session.exec(select(ChatMemory).where(ChatMemory.customer_id == customer_id)).first() is None


@pytest.mark.parametrize(
    ("message", "food"),
    [
        ("How much is jollof rice?", True),
        ("Una get afang today?", True),
        ("Is the food ready?", True),
        ("What's today's special?", True),
        ("How was your day?", False),
        ("I'm so tired today", False),
        ("My boss bought me rice, what do you think?", False),
        ("I love jollof", False),  # not a question
    ],
)
def test_is_food_question(message: str, food: bool) -> None:
    character = CharacterCreate(name="Bisi", menu=MENU)
    assert is_food_question(message, character) is food


# --- Surprise jara -----------------------------------------------------------------------


def test_surprise_jara(client: TestClient, session: Session, stand, monkeypatch) -> None:
    monkeypatch.setattr(customa_events, "surprise_roll", lambda one_in: True)
    key = sign_up(client)  # plate 1: surprise is off, nothing
    vendor = {"Authorization": "Bearer *"}

    r = client.put(f"{VENDOR}/delights/surprise", json={"enabled": True}, headers=vendor)
    assert r.status_code == 200 and r.json()["surprise_enabled"] is True
    plate2 = next_plate(client, session, key)
    assert plate2["plate_number"] == 2
    assert plate2["jara"] is not None and plate2["surprise"] is True

    monkeypatch.setattr(customa_events, "surprise_roll", lambda one_in: False)
    plate3 = next_plate(client, session, key)
    assert plate3["jara"] is None and plate3["surprise"] is False

    client.put(f"{VENDOR}/delights/surprise", json={"enabled": False}, headers=vendor)
    monkeypatch.setattr(customa_events, "surprise_roll", lambda one_in: True)
    for plate in (4, 5):
        assert next_plate(client, session, key)["jara"] is None
    plate6 = next_plate(client, session, key)
    assert plate6["jara"] is not None and plate6["surprise"] is False  # the normal jara


def test_delights_are_for_stand_members_only(client: TestClient, stand) -> None:
    assert client.get(f"{VENDOR}/delights").status_code == 401
    assert client.put(f"{VENDOR}/delights/surprise", json={"enabled": True}).status_code == 401
