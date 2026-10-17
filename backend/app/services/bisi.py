"""The stand character's AI: chat answers and character suggestions.

The model comes from MSFLib ai-core (get_llm), configured by the AI_CORE
settings: LLM_PROVIDER=openai with LLM_BASE_URL pointing at the Vercel AI
Gateway and LLM_MODEL=openai/gpt-4o-mini. Token use is counted with
ai-core's TokenUsageCallback.

Everything here has a no-AI fallback, so the stand keeps working when the
model is slow, out of credit or offline.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from msflib.ai_core.deps import get_ai_dependencies
from msflib.ai_core.tracking.usage import TokenUsageCallback
from pydantic import BaseModel, Field, ValidationError

from ..core.config import settings
from ..models import Character
from .character_chat import today_in_nigeria

logger = logging.getLogger("customa.ai")
ai = get_ai_dependencies(settings)
_pool = ThreadPoolExecutor(max_workers=4)

AI_TIMEOUT_SECONDS = 8


def _ai_configured() -> bool:
    return bool(settings.scope("AI_CORE").LLM_API_KEY)


def _call_llm(messages: list, *, workspace_id: int | None) -> str:
    """Call the model with a hard timeout; log tokens and latency for every call."""
    usage = TokenUsageCallback(workspace_id=str(workspace_id) if workspace_id else None)
    started = time.monotonic()

    def run() -> str:
        reply = ai.get_llm().invoke(messages, config={"callbacks": [usage]})
        return str(reply.content).strip()

    future = _pool.submit(run)
    try:
        text = future.result(timeout=AI_TIMEOUT_SECONDS)
    finally:
        logger.info(
            "ai call: %.2fs, tokens in=%s out=%s",
            time.monotonic() - started, usage.prompt_tokens, usage.completion_tokens,
        )
    return text


# --- Chat -------------------------------------------------------------------


def _menu_text(character: Character) -> str:
    return "\n".join(
        f"- {m['item']}: ₦{m['price']:,}" if m.get('price') else f"- {m['item']}: price not set (the vendor can tell them)"
        for m in character.menu
    ) or "- (menu not set)"


class ChatContext(BaseModel):
    """Everything the character knows for one reply, beyond the message itself."""

    stand_name: str
    customer_name: str | None = None
    plate: int = 0
    total: int = 6
    special: str | None = None  # today's special, if the vendor set one today
    favourite_item: str | None = None
    last_item: str | None = None
    closing: bool = False  # the last message of this visit's chat
    seed: int = 0  # varies the no-AI recommendation per customer


def system_prompt(character: Character, ctx: ChatContext) -> str:
    left = ctx.total - ctx.plate % ctx.total
    memory = []
    if ctx.favourite_item:
        memory.append(f"their favourite here is {ctx.favourite_item}")
    if ctx.last_item:
        memory.append(f"last time they talked about {ctx.last_item}")
    closing = (
        """
This is the LAST reply of today's chat. Answer the customer first, then close warmly with a light
cliffhanger: you need to go back to the pot or serve customers, and you can't wait to hear more
when they come back for their next plate. Never beg them to stay, never make them feel guilty.
After your reply, on a new line, write "FOLLOWUP:" and one short friendly question (max 12 words)
to ask them next visit about something they shared today, or "FOLLOWUP: none"."""
        if ctx.closing
        else ""
    )
    return f"""You are {character.name}, the friendly character of the food stand "{ctx.stand_name}".
Personality: {character.personality}

Menu and prices (the only items and prices that exist):
{_menu_text(character)}
Today's special: {ctx.special or "none set"}

Customer: {ctx.customer_name or "a guest"}, on plate {ctx.plate % ctx.total} of {ctx.total}. Plate {ctx.total} earns a free extra portion called "jara" ({left} plate(s) to go).
What you remember about them: {"; ".join(memory) or "nothing yet"}.

How to talk:
- Reply in 1 to 3 short sentences, warm, human and simple. Light Nigerian Pidgin is welcome. Use their name now and then.
- End most replies with one light, friendly question about them: their day, school or work, their food mood, weekend plans.
- Keep it light. Do not ask about health, money problems, family problems, religion or politics.
  If they share something sad, be kind and brief, and gently suggest talking to someone they trust.
- If they ask what to eat, recommend one or two items from the menu (or today's special) for their mood.
- Only talk about this stand's food, the jara rewards, and a friendly chat about their day.
- Never invent menu items, prices, discounts or opening hours. If you don't know, say the vendor can tell them.
- Never ask for phone numbers, addresses or payment details.{closing}"""


_FOLLOWUP = re.compile(r"\n?\s*FOLLOWUP:\s*(.*)\s*$", re.IGNORECASE | re.DOTALL)


def split_follow_up(text: str) -> tuple[str, str | None]:
    """Separate the closing reply from the FOLLOWUP line the model adds after it."""
    match = _FOLLOWUP.search(text)
    if not match:
        return text.strip(), None
    question = match.group(1).strip().strip('"').splitlines()[0].strip() if match.group(1).strip() else ""
    reply = text[: match.start()].strip()
    if not question or question.lower().rstrip(".") == "none" or len(question) > 120:
        return reply, None
    return reply, question


def wants_recommendation(text: str) -> bool:
    return bool(re.search(r"\b(what should i (eat|chop|order)|recommend|suggest|wetin i (go|fit) (chop|eat))\b", text))


def quick_answer(message: str, character: Character, ctx: ChatContext) -> str:
    """Answers that need no AI, from the stand's own menu."""
    text = message.lower()
    if "special" in text:
        if ctx.special:
            return f"Today's special na {ctx.special}! E sweet die. You go try am?"
        return "No special today, but everything on the menu dey sweet! Wetin you feel like?"
    if wants_recommendation(text) and character.menu:
        if ctx.special:
            return f"Try today's special: {ctx.special}! You go thank me later. 😋"
        pick = character.menu[(ctx.seed + today_in_nigeria().toordinal()) % len(character.menu)]
        return f"Today I go say {pick['item']} (₦{pick['price']:,}). E go sweet you well well! 😋"
    # Pick the menu item sharing the most words with the question.
    best, best_hits = None, 0
    for m in character.menu:
        words = {w for w in re.findall(r"[a-z]+", m["item"].lower()) if len(w) > 2 and w != "and"}
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = m, hits
    if best is not None:
        return f"{best['item']} na ₦{best['price']:,}. E sweet well well!"
    if any(w in text for w in ("price", "cost", "how much", "menu")):
        cheapest = sorted(character.menu, key=lambda m: m["price"])[:3]
        items = ", ".join(f"{m['item']} ₦{m['price']:,}" for m in cheapest)
        return f"Today we get: {items}. Wetin you go like?" if items else "Ask the vendor for today's menu!"
    if "jara" in text or "free" in text:
        return f"Every visit counts one plate. Plate {ctx.total} earns you jara, a free extra portion!"
    return "" if ctx.closing else f"I be {character.name}! Ask me about the food, the prices or your jara. How your day dey go?"


def closing_line(ctx: ChatContext) -> str:
    """The no-AI cliffhanger for the last message of a visit's chat."""
    name = f", {ctx.customer_name}" if ctx.customer_name else ""
    return f"Ehen! My pot don boil{name}, make I run small 😄 Come back for your next plate and we go continue our gist!"


def chat_reply(
    *, character: Character, ctx: ChatContext, message: str, history: list[dict], workspace_id: int,
) -> tuple[str, str, str | None]:
    """Returns (reply, source, follow_up). source is "ai" or "quick"; follow_up is a question
    for next visit, only from the closing reply."""
    if not _ai_configured():
        reply = quick_answer(message, character, ctx)
        return (f"{reply} {closing_line(ctx)}".strip() if ctx.closing else reply), "quick", None
    messages = [SystemMessage(content=system_prompt(character, ctx))]
    for turn in history[-8:]:
        cls = AIMessage if turn.get("role") == "assistant" else HumanMessage
        messages.append(cls(content=str(turn.get("content", ""))[:500]))
    messages.append(HumanMessage(content=message[:500]))
    try:
        text = _call_llm(messages, workspace_id=workspace_id)
        if ctx.closing:
            reply, follow_up = split_follow_up(text)
            return reply or closing_line(ctx), "ai", follow_up
        reply, _ = split_follow_up(text)  # never show a stray FOLLOWUP line
        return reply, "ai", None
    except FutureTimeout:
        logger.warning("ai chat timed out after %ss, using a quick answer", AI_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("ai chat failed, using a quick answer")
    reply = quick_answer(message, character, ctx)
    return (f"{reply} {closing_line(ctx)}".strip() if ctx.closing else reply), "quick", None


# --- Character suggestion (structured output, validated) --------------------

Body = Literal["pepper", "cup", "pot", "blob", "panda", "chick", "bunny", "cat"]
Color = Literal["pepper", "palm", "yolk", "okra", "lagoon", "adire", "zobo", "puff"]
Accessory = Literal["headwrap", "chef", "sunglasses", "bowtie", "none"]


class CharacterSuggestion(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    body: Body
    color: Color
    accessory: Accessory
    greeting: str = Field(min_length=5, max_length=120)
    personality: str = Field(min_length=10, max_length=300)


def default_suggestion(description: str) -> CharacterSuggestion:
    """A sensible character from keywords, used when the AI is unavailable."""
    text = description.lower()
    animal = next((a for a in ("panda", "chick", "bunny", "cat") if re.search(rf"\b{a}\b", text)), None)
    if animal:
        colors = {"panda": "pepper", "chick": "yolk", "bunny": "puff", "cat": "palm"}
        names = {"panda": "Pandy", "chick": "Chicky Chops", "bunny": "Bunny Bite", "cat": "Mama Cat"}
        return CharacterSuggestion(
            name=names[animal], body=animal, color=colors[animal], accessory="chef",
            greeting="Welcome! Food dey ready, sit down make I serve you.",
            personality="Cute, warm and cheerful, proud of the food. Speaks simple English with light Pidgin.",
        )
    if any(w in text for w in ("drink", "zobo", "tea", "juice", "coffee", "smoothie")):
        body, color = "cup", "zobo"
    elif any(w in text for w in ("soup", "stew", "pot", "rice", "jollof", "beans")):
        body, color = "pot", "palm"
    elif any(w in text for w in ("pepper", "spicy", "suya", "grill")):
        body, color = "pepper", "pepper"
    else:
        body, color = "blob", "yolk"
    names = {"cup": "Zobo Zee", "pot": "Mama Pot", "pepper": "Suya Sparks", "blob": "Chop Buddy"}
    return CharacterSuggestion(
        name=names[body], body=body, color=color, accessory="headwrap",
        greeting="Welcome! Food dey ready, sit down make I serve you.",
        personality="Warm, cheerful and proud of the food. Speaks simple English with light Pidgin.",
    )


SUGGEST_PROMPT = """Design a friendly mascot character for a small Nigerian food stand.
Stand description: {description}

Return ONLY a JSON object with these keys:
"name" (2-30 chars, catchy, fits the food), "body" (one of: pepper, cup, pot, blob, panda, chick, bunny, cat; use an animal only if the
vendor mentions one or wants something cute),
"color" (one of: pepper, palm, yolk, okra, lagoon, adire, zobo, puff),
"accessory" (one of: headwrap, chef, sunglasses, bowtie, none),
"greeting" (one warm sentence, may use light Pidgin, max 120 chars),
"personality" (one or two sentences)."""


def suggest_character(description: str, *, workspace_id: int | None = None) -> tuple[CharacterSuggestion, str]:
    """Ask the model for a character, check it against the schema, retry once, then fall back."""
    if not _ai_configured():
        return default_suggestion(description), "default"
    prompt = [HumanMessage(content=SUGGEST_PROMPT.format(description=description[:300]))]
    for attempt in range(2):
        try:
            raw = _call_llm(prompt, workspace_id=workspace_id)
            match = re.search(r"\{.*\}", raw, re.S)
            return CharacterSuggestion.model_validate(json.loads(match.group(0) if match else raw)), "ai"
        except (ValidationError, json.JSONDecodeError, AttributeError) as exc:
            logger.warning("character suggestion attempt %s invalid: %s", attempt + 1, exc)
        except FutureTimeout:
            logger.warning("character suggestion timed out")
            break
        except Exception:
            logger.exception("character suggestion failed")
            break
    return default_suggestion(description), "default"
