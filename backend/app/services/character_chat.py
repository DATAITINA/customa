"""The rules around chatting with a stand's character (the AI itself is in services/bisi.py).

- Private: the vendor only ever sees food questions (is_food_question), never the rest.
- Short and warm: each counted plate opens one chat of CHAT_MESSAGES_PER_PLATE messages. The
  last reply ends with a warm cliffhanger, and the next plate picks the chat up from there.
- Memory the customer can see and clear: a favourite dish, the last dish talked about, and one
  follow-up question for next time (ChatMemory).
"""

import re
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, select

from ..actions import visit_action
from ..core.config import CustomaSettings
from ..models import Character, ChatMemory, Customer, Visit

# Nigeria is UTC+1 all year (no daylight saving).
NIGERIA = timedelta(hours=1)

# --- Today's special ----------------------------------------------------------------------


def today_in_nigeria() -> date:
    return (datetime.now(UTC) + NIGERIA).date()


def todays_special(stand_settings: CustomaSettings) -> str | None:
    """The vendor's special, only on the day it was set."""
    text = (stand_settings.TODAYS_SPECIAL or "").strip()
    if not text or stand_settings.TODAYS_SPECIAL_DATE != today_in_nigeria().isoformat():
        return None
    return text


# --- Food questions: the only chat a vendor sees ------------------------------------------

_FOOD_WORDS = {
    "food", "menu", "price", "prices", "cost", "naira", "chop", "eat", "plate", "plates", "portion",
    "rice", "jollof", "fried", "soup", "stew", "sauce", "meat", "fish", "chicken", "beef", "goat",
    "turkey", "egg", "eggs", "beans", "yam", "plantain", "dodo", "swallow", "fufu", "eba", "garri",
    "amala", "semo", "pounded", "afang", "edikang", "ikong", "egusi", "okra", "ogbono", "pepper",
    "spicy", "suya", "noodles", "spaghetti", "salad", "drink", "drinks", "water", "juice", "zobo",
    "coke", "malt", "tea", "special", "jara", "takeaway", "pack", "delivery", "order", "available",
    "ready", "finish", "finished", "hot", "open", "close", "closing", "opening", "extra",
}
_QUESTION_WORDS = (
    "how much", "how many", "what", "wetin", "which", "do you", "do una", "una get", "you get",
    "is there", "are there", "any ", "can i", "can you", "when", "where", "abeg", "is the", "is your",
    "e remain", "e dey", "una dey", "you dey",
)
# Anything personal stays private, even with a food word in it ("my boss bought me rice").
_PERSONAL = re.compile(
    r"\b(i feel|i'm sad|im sad|i am sad|depress|lonely|stress|my (girlfriend|boyfriend|babe|wife|husband|"
    r"mum|mom|mother|dad|father|family|brother|sister|boss|exam|exams|interview|work|job|school|health|"
    r"money|rent|life))\b"
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def mentioned_item(message: str, character: Character) -> str | None:
    """The menu item a message is about: the one sharing the most words with it."""
    said = _words(message)
    best, best_hits = None, 0
    for m in character.menu or []:
        words = {w for w in _words(str(m.get("item", ""))) if len(w) > 2 and w != "and"}
        hits = len(words & said)
        if hits > best_hits:
            best, best_hits = str(m["item"]), hits
    return best


def is_food_question(message: str, character: Character) -> bool:
    """True for a question about this stand's food (price, menu, what is ready...).

    These, and only these, are shown to the vendor. When unsure, the answer is False: a
    vendor missing a food question is fine, a customer's private chat reaching the vendor is not.
    """
    text = message.lower().strip()
    if not text or len(text) > 160 or _PERSONAL.search(text):
        return False
    is_question = "?" in text or any(text.startswith(q) or f" {q}" in text for q in _QUESTION_WORDS)
    if not is_question:
        return False
    return bool(_words(text) & _FOOD_WORDS) or mentioned_item(text, character) is not None


# --- Memory ------------------------------------------------------------------------------

_LOVE = re.compile(r"\b(i (really )?(like|love|enjoy)|my (favourite|favorite|fave|best)|i dey (like|love|enjoy))\b")


def memory_for(session: Session, *, customer: Customer) -> ChatMemory:
    """This customer's chat memory row, created on first use. Locked for this transaction so
    two messages sent at once cannot both take the last slot."""
    row = session.exec(
        select(ChatMemory).where(ChatMemory.customer_id == customer.id).with_for_update()
    ).first()
    if row is None:
        row = ChatMemory(workspace_id=customer.workspace_id, customer_id=customer.id)
        session.add(row)
        session.flush()
    return row


def remember_from_message(memory: ChatMemory, message: str, character: Character) -> None:
    item = mentioned_item(message, character)
    if item is None:
        return
    memory.last_item = item
    if _LOVE.search(message.lower()):
        memory.favourite_item = item


def memory_view(memory: ChatMemory | None) -> dict[str, str | None]:
    return {
        "favourite_item": memory.favourite_item if memory else None,
        "last_item": memory.last_item if memory else None,
        "follow_up": memory.follow_up if memory else None,
    }


def forget_memory(memory: ChatMemory) -> None:
    """The customer's "forget" button: clear what the character remembers (not the plate count)."""
    memory.favourite_item = None
    memory.last_item = None
    memory.follow_up = None


def delete_memory(session: Session, *, customer: Customer) -> None:
    """Delete-my-data: remove the row completely."""
    row = session.exec(select(ChatMemory).where(ChatMemory.customer_id == customer.id)).first()
    if row is not None:
        session.delete(row)
        session.flush()


# --- One chat per plate ------------------------------------------------------------------


def plates_to_jara(last: Visit | None, stand_settings: CustomaSettings) -> int:
    plate = last.plate_number if last else 0
    return stand_settings.PLATES_FOR_JARA - plate % stand_settings.PLATES_FOR_JARA


def opener_for(
    memory: ChatMemory,
    *,
    character: Character,
    customer: Customer,
    last: Visit | None,
    stand_settings: CustomaSettings,
) -> str:
    """The character's first line this visit: picks up last visit's chat when there is one."""
    name = customer.first_name
    hi = f"{name}! " if name else ""
    if memory.follow_up:
        line = f"{hi}You don come back! {memory.follow_up}"
    else:
        line = f"{hi}{character.greeting}"
    extras = []
    if plates_to_jara(last, stand_settings) == 1:
        extras.append("Just ONE more plate and jara na yours o! 🎉")
    special = todays_special(stand_settings)
    if special:
        extras.append(f"Today's special: {special} 🍲")
    elif memory.favourite_item:
        extras.append(f"Your favourite {memory.favourite_item} today?")
    return " ".join([line, *extras])


def start_or_resume(
    session: Session,
    *,
    memory: ChatMemory,
    character: Character,
    customer: Customer,
    stand_settings: CustomaSettings,
) -> Visit | None:
    """Open a fresh chat when a new plate has been counted since the last one.

    The follow-up from last time goes into this visit's opener, then is cleared, so the same
    question is never asked twice. Returns the customer's last plate (None if they have none).
    """
    last = visit_action.last_for_customer(session, customer_id=customer.id)
    if last is not None and memory.visit_id != last.id:
        memory.visit_id = last.id
        memory.messages_used = 0
        memory.closed = False
        memory.opener = opener_for(
            memory, character=character, customer=customer, last=last, stand_settings=stand_settings
        )
        memory.follow_up = None
        session.add(memory)
        session.flush()
    return last


def chat_status(memory: ChatMemory, last: Visit | None, stand_settings: CustomaSettings) -> dict:
    limit = stand_settings.CHAT_MESSAGES_PER_PLATE
    is_open = last is not None and memory.visit_id == last.id and not memory.closed
    return {
        "open": is_open,
        "messages_left": max(0, limit - memory.messages_used) if is_open else 0,
        "opener": memory.opener if last is not None else None,
        "visit_id": memory.visit_id,
    }


# --- Jokes: safe, food-only, one a day ------------------------------------------------------

JOKES = [
    "Why the jollof no fit keep secret? Because e too party! 🎉",
    "Rice tell beans say: 'Na you dey always bring wahala for my belle.' 😂",
    "Wetin plantain tell yam? 'You dey too serious, learn to fry small!' 🍌",
    "My pepper soup so hot, even the spoon dey sweat. 🥵",
    "Eba and fufu dey argue who strong pass. Soup just dey laugh for corner. 🍲",
    "Why fish no dey ever late? Because e always dey on scale! 🐟",
    "Doctor say make I eat more greens. I don order extra afang. Health first! 🥬",
    "Small chops tell big chops: 'Size no matter, na taste matter.' 😄",
    "Na only food fit make person smile before e even taste am. 😋",
    "Meat tell rice: 'Without me, you no complete.' Rice say: 'Without me, where you go sit?' 😂",
]


def joke_of_the_day(salt: int = 0) -> str:
    return JOKES[(today_in_nigeria().toordinal() + salt) % len(JOKES)]


def wants_joke(message: str) -> bool:
    return bool(re.search(r"\b(joke|jokes|make me laugh|funny)\b", message.lower()))
