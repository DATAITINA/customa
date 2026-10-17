"""Plan the next visit: "When you go come back?"

After a plate is counted the character asks for a day (today, tomorrow or the next 6 days) and a
time (morning, lunch or evening). Both are needed: people who write down a date AND a time follow
through more often (Milkman et al., PNAS 2011). It is a plan, never a reservation: the vendor
holds no food for anybody.

- One active plan per customer per stand; the customer can change or cancel it.
- A reminder about 1 hour before the time slot: by web push if the customer turned alerts on at
  this stand, or by SMS only where the stand turned PLAN_SMS_REMINDERS on and the customer already
  agreed to texts there. The scheduler (GET /cron/plan-reminders, every 15 minutes) claims each
  reminder by setting reminder_sent_at first, so it never goes twice.
- A plate counted during the planned day and slot (30 minutes' grace either side) keeps the plan:
  "You keep your word! 🙌". A missed plan is never a guilt trip: next visit, "No wahala, life
  happen 😄", and a new plan.
Times are Nigeria time (UTC+1); stored times are UTC.
"""

import json
import logging
from concurrent.futures import wait
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, select

from ..actions import character_action
from ..core.config import CustomaSettings, settings
from ..models import Customer, PushSubscription, SmsSubscription, Visit, VisitPlan, Workspace
from . import alerts, sms_alerts
from .character_chat import NIGERIA
from .stands import resolve_stand_settings

logger = logging.getLogger("customa.plans")

# Slot: (start hour, end hour) in Nigeria time, the label and its hours.
SLOTS: dict[str, tuple[int, int, str, str]] = {
    "morning": (7, 11, "Morning", "7–11am"),
    "lunch": (11, 15, "Lunch", "11am–3pm"),
    "evening": (15, 21, "Evening", "3–9pm"),
}
GRACE = timedelta(minutes=30)
DAYS_AHEAD = 7  # today + the next 7 days: Today, Tomorrow and 6 more
REMIND_BEFORE = timedelta(hours=1)
SEND_DEADLINE_SECONDS = 10


class PlanError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def local_today(now: datetime) -> date:
    return (now + NIGERIA).date()


def window(day: date, slot: str) -> tuple[datetime, datetime]:
    """The slot's start and end in UTC (naive)."""
    start_h, end_h, _, _ = SLOTS[slot]
    return datetime.combine(day, time(start_h)) - NIGERIA, datetime.combine(day, time(end_h)) - NIGERIA


def day_word(day: date, today: date) -> str:
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return day.strftime("%A")


def when_text(day: date, slot: str, today: date) -> str:
    """'Thursday for lunch', 'this evening', 'tomorrow morning'."""
    word = day_word(day, today)
    if slot == "lunch":
        return f"{word} for lunch"
    part = "morning" if slot == "morning" else "evening"
    return f"this {part}" if word == "today" else f"{word} {part}"


def options(now: datetime) -> dict[str, Any]:
    """The day chips and time chips; a slot already over today is not offered."""
    today = local_today(now)
    days = []
    for n in range(DAYS_AHEAD + 1):
        d = today + timedelta(days=n)
        label = "Today" if n == 0 else "Tomorrow" if n == 1 else d.strftime("%a ") + str(d.day)
        open_slots = [s for s in SLOTS if window(d, s)[1] > now]
        days.append({"date": d.isoformat(), "label": label, "open": open_slots})
    slots = [{"key": k, "label": v[2], "hours": v[3]} for k, v in SLOTS.items()]
    return {"days": [d for d in days if d["open"]], "slots": slots}


# --- Plans ----------------------------------------------------------------------------------


def active_plan(session: Session, *, customer: Customer) -> VisitPlan | None:
    return session.exec(
        select(VisitPlan)
        .where(VisitPlan.customer_id == customer.id, VisitPlan.status == "active")
        .order_by(VisitPlan.id.desc())
    ).first()


def reminder_channel_for(
    session: Session, *, workspace: Workspace, customer: Customer, stand_settings: CustomaSettings
) -> str | None:
    """How the reminder would go: push (alerts on), sms (texts agreed and the stand allows), or None."""
    if alerts.alerts_available() and session.exec(
        select(PushSubscription.id).where(
            PushSubscription.workspace_id == workspace.id, PushSubscription.customer_id == customer.id
        )
    ).first():
        return "push"
    if stand_settings.PLAN_SMS_REMINDERS and sms_alerts.sms_available() and session.exec(
        select(SmsSubscription.id).where(
            SmsSubscription.workspace_id == workspace.id, SmsSubscription.customer_id == customer.id
        )
    ).first():
        return "sms"
    return None


def plan_view(
    session: Session, plan: VisitPlan, *, workspace: Workspace, customer: Customer,
    stand_settings: CustomaSettings, now: datetime,
) -> dict[str, Any]:
    today = local_today(now)
    _, _, label, hours = SLOTS[plan.slot]
    when = when_text(plan.day, plan.slot, today)
    return {
        "id": plan.id,
        "day": plan.day.isoformat(),
        "slot": plan.slot,
        "status": plan.status,
        "label": f"{plan.day.strftime('%A')} {plan.day.day} {plan.day.strftime('%b')} · {label} ({hours})",
        "when": when,
        "confirm": f"Deal! I go dey expect you {when} 🙌",
        "reminder": reminder_channel_for(session, workspace=workspace, customer=customer, stand_settings=stand_settings)
        if plan.reminder_due_at and not plan.reminder_sent_at
        else None,
        "reminder_at": plan.reminder_due_at,
    }


def make_plan(
    session: Session, *, workspace: Workspace, customer: Customer, day: date, slot: str, now: datetime
) -> VisitPlan:
    if slot not in SLOTS:
        raise PlanError(400, "Pick morning, lunch or evening.")
    today = local_today(now)
    if not today <= day <= today + timedelta(days=DAYS_AHEAD):
        raise PlanError(400, "Pick a day in the next week.")
    start, end = window(day, slot)
    if end <= now:
        raise PlanError(400, "That time don pass. Pick another one.")
    has_plate = session.exec(select(Visit.id).where(Visit.customer_id == customer.id)).first()
    if has_plate is None:
        raise PlanError(403, "Count your first plate, then make a plan.")
    current = active_plan(session, customer=customer)
    if current is not None:
        current.status = "cancelled"  # one active plan: the new one replaces it
        session.add(current)
    due = start - REMIND_BEFORE
    plan = VisitPlan(
        workspace_id=workspace.id,
        customer_id=customer.id,
        day=day,
        slot=slot,
        reminder_due_at=due if due > now + timedelta(minutes=5) else None,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def cancel_plan(session: Session, *, customer: Customer) -> None:
    plan = active_plan(session, customer=customer)
    if plan is not None:
        plan.status = "cancelled"
        session.add(plan)
        session.commit()


def on_plate_counted(session: Session, *, customer: Customer, visit: Visit, now: datetime) -> None:
    """A counted plate keeps the active plan (in its day and slot, with grace), or notes one
    that was missed, so the character can say so once."""
    plan = active_plan(session, customer=customer)
    if plan is not None:
        start, end = window(plan.day, plan.slot)
        if start - GRACE <= now <= end + GRACE:
            plan.status, plan.kept_visit_id, plan.noted_visit_id = "kept", visit.id, visit.id
        elif now > end + GRACE:
            plan.status, plan.noted_visit_id = "missed", visit.id
        session.add(plan)
    # A plan the scheduler already marked missed: tell the customer once, at this plate.
    for missed in session.exec(
        select(VisitPlan).where(
            VisitPlan.customer_id == customer.id, VisitPlan.status == "missed", VisitPlan.noted_visit_id.is_(None)
        )
    ).all():
        missed.noted_visit_id = visit.id
        session.add(missed)
    session.commit()


def outcome_for_visit(session: Session, visit: Visit) -> str | None:
    """'kept' or 'missed' when this plate settled a plan, else None."""
    plan = session.exec(
        select(VisitPlan).where(VisitPlan.noted_visit_id == visit.id).order_by(VisitPlan.id.desc())
    ).first()
    if plan is None:
        return None
    return "kept" if plan.status == "kept" else "missed" if plan.status == "missed" else None


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: the customer's plans (the caller commits)."""
    for plan in session.exec(select(VisitPlan).where(VisitPlan.customer_id == customer.id)).all():
        session.delete(plan)
    session.flush()


# --- Reminders (the scheduler) --------------------------------------------------------------


def reminder_push(workspace: Workspace, character_name: str | None, plan: VisitPlan, today: date) -> dict[str, Any]:
    first = (character_name or workspace.name).split(" ")[0]
    _, _, label, hours = SLOTS[plan.slot]
    return {
        "type": "plan_reminder",
        "slug": workspace.slug,
        "title": f"{first}: I go dey expect you {when_text(plan.day, plan.slot, today)} 🍲",
        "body": f"Your plan at {workspace.name}: {label.lower()}, {hours}. No pressure, see you soon!",
        "url": f"/s/{workspace.slug}",
        "tag": f"plan-{plan.id}",
    }


def reminder_text(workspace: Workspace, character_name: str | None, plan: VisitPlan, today: date) -> str:
    """One plain SMS page (no emoji)."""
    first = sms_alerts.plain((character_name or workspace.name).split(" ")[0]) or "Hi"
    stand = sms_alerts.plain(workspace.name) or "your food spot"
    _, _, label, hours = SLOTS[plan.slot]
    link = f"{settings.PUBLIC_WEB_URL.split('://', 1)[-1].rstrip('/')}/s/{workspace.slug}"
    hours_plain = hours.replace("–", "-")
    tail = f": your plan is {label.lower()} ({hours_plain}) {day_word(plan.day, today)}. No pressure! {link}"
    room = sms_alerts.SMS_LIMIT - len(tail) - len(first) - len(" at ")
    if len(stand) > room:
        stand = stand[: max(0, room - 1)].rstrip() + "."
    return f"{first} at {stand}{tail}"[: sms_alerts.SMS_LIMIT]


def _claim(session: Session, plan_id: int, now: datetime) -> bool:
    """Set reminder_sent_at only if still unset: two scheduler runs never both send."""
    result = session.execute(
        update(VisitPlan)
        .where(VisitPlan.id == plan_id, VisitPlan.reminder_sent_at.is_(None))
        .values(reminder_sent_at=now)
    )
    session.commit()
    return result.rowcount == 1


def run_reminders(session: Session, *, now: datetime) -> dict[str, int]:
    """Send the reminders that are due and mark plans whose slot is long over as missed."""
    counts = {"push": 0, "sms": 0, "none": 0, "missed": 0}
    due = session.exec(
        select(VisitPlan).where(
            VisitPlan.status == "active", VisitPlan.reminder_due_at.is_not(None),
            VisitPlan.reminder_due_at <= now, VisitPlan.reminder_sent_at.is_(None),
        )
    ).all()
    for plan in due:
        if not _claim(session, plan.id, now):
            continue
        workspace = session.get(Workspace, plan.workspace_id)
        customer = session.get(Customer, plan.customer_id)
        if workspace is None or customer is None or window(plan.day, plan.slot)[1] <= now:
            channel = "none"  # too late to be useful
        else:
            stand_settings = resolve_stand_settings(session, workspace)
            channel = reminder_channel_for(session, workspace=workspace, customer=customer, stand_settings=stand_settings) or "none"
            character = character_action.get_for_stand(session, workspace_id=workspace.id)
            today = local_today(now)
            if channel == "push":
                payload = json.dumps(reminder_push(workspace, character.name if character else None, plan, today))
                subs = [
                    {"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}
                    for s in session.exec(
                        select(PushSubscription).where(
                            PushSubscription.workspace_id == workspace.id, PushSubscription.customer_id == customer.id
                        )
                    ).all()
                ]
                ttl = max(60, int((window(plan.day, plan.slot)[1] - now).total_seconds()))
                futures = [alerts._pool.submit(alerts._send_one, sub, payload, ttl) for sub in subs]
                wait(futures, timeout=SEND_DEADLINE_SECONDS)
            elif channel == "sms":
                phone = session.exec(
                    select(SmsSubscription.phone).where(
                        SmsSubscription.workspace_id == workspace.id, SmsSubscription.customer_id == customer.id
                    )
                ).first()
                text = reminder_text(workspace, character.name if character else None, plan, today)
                if not phone or sms_alerts.send_chunk([phone], text) != 1:
                    channel = "none"
        plan = session.get(VisitPlan, plan.id)
        plan.reminder_channel = channel
        session.add(plan)
        session.commit()
        counts[channel] += 1

    for plan in session.exec(select(VisitPlan).where(VisitPlan.status == "active")).all():
        if window(plan.day, plan.slot)[1] + GRACE < now:
            plan.status = "missed"
            session.add(plan)
            counts["missed"] += 1
    session.commit()
    logger.info("plan reminders: %s", counts)
    return counts


# --- The vendor's view ----------------------------------------------------------------------


def effective_status(plan: VisitPlan, now: datetime) -> str:
    """'missed' for an active plan whose slot is over, even before the scheduler marks it."""
    if plan.status == "active" and window(plan.day, plan.slot)[1] + GRACE < now:
        return "missed"
    return plan.status


def vendor_summary(session: Session, *, workspace: Workspace, now: datetime) -> dict[str, Any]:
    """'Coming today: 7 (lunch 4 · evening 3)' with first names where given, and 'Plans kept
    this week: 5 of 8' (the last 7 days, plans whose time is over)."""
    today = local_today(now)
    rows = session.exec(
        select(VisitPlan, Customer)
        .join(Customer, Customer.id == VisitPlan.customer_id)
        .where(VisitPlan.workspace_id == workspace.id, VisitPlan.day >= today - timedelta(days=6), VisitPlan.day <= today)
    ).all()
    by_slot = {s: 0 for s in SLOTS}
    names: list[dict[str, Any]] = []
    kept = settled = 0
    for plan, customer in rows:
        status = effective_status(plan, now)
        if plan.day == today and status in ("active", "kept"):
            by_slot[plan.slot] += 1
            if customer.first_name:
                names.append({"name": customer.first_name, "slot": plan.slot, "came": status == "kept"})
        if status in ("kept", "missed"):
            settled += 1
            kept += status == "kept"
    return {
        "coming_today": {"total": sum(by_slot.values()), "by_slot": by_slot, "names": names},
        "kept_week": {"kept": kept, "total": settled},
    }
