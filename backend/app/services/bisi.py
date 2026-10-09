"""The stand character's AI: chat answers and character suggestions.

The model comes from MSFLib ai-core (get_llm), configured by the AI_CORE
settings: LLM_PROVIDER=openai with LLM_BASE_URL pointing at the Vercel AI
Gateway and LLM_MODEL=anthropic/claude-haiku-4.5. Token use is counted with
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
    return "\n".join(f"- {m['item']}: ₦{m['price']}" for m in character.menu) or "- (menu not set)"


def system_prompt(character: Character, stand_name: str, customer_name: str | None, plate: int, total: int) -> str:
    return f"""You are {character.name}, the friendly character of the food stand "{stand_name}".
Personality: {character.personality}

Menu and prices (the only items and prices that exist):
{_menu_text(character)}

Customer: {customer_name or "a guest"}, on plate {plate} of {total}. Plate {total} earns a free extra portion called "jara".

Rules:
- Reply in 1 to 3 short sentences, warm and simple. Light Nigerian Pidgin is welcome.
- Only talk about this stand: the food, prices, the jara rewards, and a friendly chat about the customer's day.
- Never invent menu items, prices, discounts or opening hours. If you don't know, say the vendor can tell them.
- Politely decline politics, religion, medical, legal or money advice, and steer back to the food.
- Never ask for phone numbers, addresses or payment details."""


def quick_answer(message: str, character: Character, total: int) -> str:
    """Answers that need no AI, from the stand's own menu."""
    text = message.lower()
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
        return f"Every visit counts one plate. Plate {total} earns you jara, a free extra portion!"
    return f"I be {character.name}! Ask me about the food, the prices or your jara."


def chat_reply(
    *, character: Character, stand_name: str, customer_name: str | None, plate: int, total: int,
    message: str, history: list[dict], workspace_id: int,
) -> tuple[str, str]:
    """Returns (reply, source) where source is "ai" or "quick"."""
    if not _ai_configured():
        return quick_answer(message, character, total), "quick"
    messages = [SystemMessage(content=system_prompt(character, stand_name, customer_name, plate, total))]
    for turn in history[-8:]:
        cls = AIMessage if turn.get("role") == "assistant" else HumanMessage
        messages.append(cls(content=str(turn.get("content", ""))[:500]))
    messages.append(HumanMessage(content=message[:500]))
    try:
        return _call_llm(messages, workspace_id=workspace_id), "ai"
    except FutureTimeout:
        logger.warning("ai chat timed out after %ss, using a quick answer", AI_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("ai chat failed, using a quick answer")
    return quick_answer(message, character, total), "quick"


# --- Character suggestion (structured output, validated) --------------------

Body = Literal["pepper", "cup", "pot", "blob"]
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
"name" (2-30 chars, catchy, fits the food), "body" (one of: pepper, cup, pot, blob),
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
