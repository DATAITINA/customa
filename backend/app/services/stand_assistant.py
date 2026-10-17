"""Ask about your stand: a vendor's AI helper, run by MSFLib ai-api's agent router.

The vendor asks in plain words ("How did this week go?", "When am I busiest?", "Who are my
regulars?") and the agent answers from the stand's own numbers, through read-only tools.

How it is wired (MSFLib, as documented):
- msflib.ai_api.router.create_agent_router mounts /stands/{slug}/assistant/ask behind vendor
  login (msflib-auth) and the stand membership check; it builds a LangChain agent from our tools
  (an ai-core StaticToolRegistry) and the same ai-core LLM the character chat uses.
- ai-api passes a ScopeEnvelope (workspace_id = this stand) to every tool call through the
  LangGraph runtime context; each tool reads only that stand. A tool never trusts a stand id
  from the model.
- Privacy: tools return first names only where the customer gave one, never phone numbers,
  chats or customer keys.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from msflib.ai_core.services.tool_registry import StaticToolRegistry
from sqlmodel import Session, func, select

from app.db.session import engine
from app.models import Character, Customer, JaraReward, Payment, Rating, Visit, Workspace

NIGERIA = timedelta(hours=1)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SYSTEM_PROMPT = (
    "You are Customa's business helper for a Nigerian food vendor, talking about their own food "
    "stand. Answer in short, warm, simple English (a little Pidgin is fine), in 2 to 5 sentences "
    "or a short list. Always call a tool to get numbers: never guess or invent numbers, names, "
    "prices or dates. If the numbers are too few to say much, say so kindly. End with one small, "
    "practical tip the vendor can try this week (e.g. a plan for the busiest time, greeting "
    "regulars, the prize wheel, leftover-food alerts). Never ask for or reveal phone numbers."
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _days(days: int) -> int:
    return max(1, min(int(days or 7), 90))


# --- Read-only numbers for one stand (plain functions, tested directly) ---------------------


def stand_summary(session: Session, workspace_id: int, days: int = 7) -> dict[str, Any]:
    days = _days(days)
    since = _now() - timedelta(days=days)
    visits = session.exec(select(Visit).where(Visit.workspace_id == workspace_id, Visit.created_at >= since)).all()
    customers = {v.customer_id for v in visits}
    first_seen = dict(
        session.exec(
            select(Visit.customer_id, func.min(Visit.created_at))
            .where(Visit.workspace_id == workspace_id, Visit.customer_id.in_(customers) if customers else False)
            .group_by(Visit.customer_id)
        ).all()
    ) if customers else {}
    new = sum(1 for c in customers if first_seen.get(c) and first_seen[c] >= since)
    stars = session.exec(select(func.avg(Rating.stars), func.count()).where(Rating.workspace_id == workspace_id, Rating.created_at >= since)).one()
    jara = session.exec(select(func.count()).select_from(JaraReward).where(JaraReward.workspace_id == workspace_id, JaraReward.created_at >= since)).one()
    paid = session.exec(
        select(func.coalesce(func.sum(Payment.amount_naira), 0), func.count())
        .where(Payment.workspace_id == workspace_id, Payment.status == "paid", Payment.created_at >= since)
    ).one()
    by_day = Counter((v.created_at + NIGERIA).date() for v in visits)
    best = max(by_day.items(), key=lambda kv: kv[1]) if by_day else None
    return {
        "period_days": days,
        "plates_counted": len(visits),
        "customers": len(customers),
        "new_customers": new,
        "returning_customers": len(customers) - new,
        "jara_earned": jara,
        "ratings": stars[1],
        "average_stars_out_of_5": round(float(stars[0]), 1) if stars[0] is not None else None,
        "paid_in_customa_naira": int(paid[0]),
        "paid_plates": paid[1],
        "best_day": {"date": best[0].isoformat(), "weekday": DAYS[best[0].weekday()], "plates": best[1]} if best else None,
    }


def busiest_times(session: Session, workspace_id: int, days: int = 28) -> dict[str, Any]:
    days = _days(days)
    since = _now() - timedelta(days=days)
    times = [t + NIGERIA for t in session.exec(select(Visit.created_at).where(Visit.workspace_id == workspace_id, Visit.created_at >= since)).all()]
    slot = lambda h: "morning (7-11am)" if h < 11 else "lunch (11am-3pm)" if h < 15 else "evening (3-9pm)"
    return {
        "period_days": days,
        "plates": len(times),
        "by_weekday": {DAYS[d]: n for d, n in sorted(Counter(t.weekday() for t in times).items())},
        "by_time_of_day": dict(Counter(slot(t.hour) for t in times).most_common()),
        "busiest_hours": [f"{h}:00" for h, _ in Counter(t.hour for t in times).most_common(3)],
    }


def top_regulars(session: Session, workspace_id: int, limit: int = 5) -> dict[str, Any]:
    limit = max(1, min(int(limit or 5), 10))
    rows = session.exec(
        select(Customer.first_name, Customer.consent, func.count(Visit.id), func.max(Visit.created_at))
        .join(Visit, Visit.customer_id == Customer.id)
        .where(Customer.workspace_id == workspace_id)
        .group_by(Customer.id, Customer.first_name, Customer.consent)
        .order_by(func.count(Visit.id).desc())
        .limit(limit)
    ).all()
    return {
        "regulars": [
            {
                "name": (name if consent and name else "A regular (no name given)"),
                "plates": plates,
                "last_visit_days_ago": (_now() - last).days,
            }
            for name, consent, plates, last in rows
        ]
    }


def menu_and_prices(session: Session, workspace_id: int) -> dict[str, Any]:
    ch = session.exec(select(Character).where(Character.workspace_id == workspace_id)).first()
    menu = ch.menu if ch else []
    return {"menu": [{"item": m.get("item"), "price_naira": m.get("price") or None} for m in menu if isinstance(m, dict)]}


# --- LangChain tools: the stand comes from ai-api's scope, never from the model -----------


def _workspace_id() -> int:
    runtime = get_runtime()
    scope = getattr(getattr(runtime, "context", None), "scope", None)
    value = scope.get_dim("workspace_id") if scope is not None else None
    if not value:
        raise ValueError("No stand in scope")
    return int(value)


def open_session() -> Session:
    """A database session for one tool call (tests point this at their own database)."""
    return Session(engine)


def _run(fn, **kwargs) -> dict[str, Any]:
    with open_session() as session:
        return fn(session, _workspace_id(), **kwargs)


@tool
def get_stand_summary(days: int = 7) -> dict[str, Any]:
    """Plates, customers (new and returning), jara, ratings, payments and the best day for the
    last `days` days (1-90) at this vendor's stand."""
    return _run(stand_summary, days=days)


@tool
def get_busiest_times(days: int = 28) -> dict[str, Any]:
    """When customers come: plates by weekday, by time of day and the busiest hours (Nigeria time)
    over the last `days` days (1-90)."""
    return _run(busiest_times, days=days)


@tool
def get_top_regulars(limit: int = 5) -> dict[str, Any]:
    """The stand's most loyal customers: first name (only if they gave it), plates, days since
    their last visit."""
    return _run(top_regulars, limit=limit)


@tool
def get_menu_and_prices() -> dict[str, Any]:
    """The stand's menu with prices in naira."""
    return _run(menu_and_prices)


TOOLS = [get_stand_summary, get_busiest_times, get_top_regulars, get_menu_and_prices]


def tool_registries() -> list[StaticToolRegistry]:
    return [StaticToolRegistry(TOOLS)]


def stand_for_vendor(workspace: Workspace) -> Workspace:
    """ai-api's workspace dependency: the stand from the path, already membership-checked."""
    return workspace
