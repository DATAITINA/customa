"""Plan the next visit: the customer's plan (no login, the customer's key), its calendar file,
and the scheduler's reminder run. Rules: app/services/visit_plans.py."""

import hmac
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.actions import customer_action
from app.api import deps
from app.api.api_v1.endpoints.public import require_customer
from app.core.config import settings
from app.models import Customer, Workspace
from app.services import visit_plans
from app.services.stands import resolve_stand_settings
from app.services.visit_plans import PlanError

public_router = APIRouter(prefix="/public/{workspace_slug}/plan", tags=["visit_plans"])
cron_router = APIRouter(prefix="/cron", tags=["visit_plans"])


class PlanRequest(BaseModel):
    day: date
    slot: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _state(session: Session, workspace: Workspace, customer: Customer) -> dict[str, Any]:
    now = _now()
    stand_settings = resolve_stand_settings(session, workspace)
    plan = visit_plans.active_plan(session, customer=customer)
    return {
        "plan": visit_plans.plan_view(
            session, plan, workspace=workspace, customer=customer, stand_settings=stand_settings, now=now
        )
        if plan
        else None,
        "options": visit_plans.options(now),
        # How a reminder would reach this customer now: push, sms or None (then: "turn on alerts").
        "reminder": visit_plans.reminder_channel_for(
            session, workspace=workspace, customer=customer, stand_settings=stand_settings
        ),
    }


@public_router.get("")
def read_plan(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return _state(session, workspace, customer)


@public_router.put("")
def make_plan(
    body: PlanRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Make (or change) the plan: a day and a time slot, both required. One active plan."""
    try:
        visit_plans.make_plan(session, workspace=workspace, customer=customer, day=body.day, slot=body.slot, now=_now())
    except PlanError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return _state(session, workspace, customer)


@public_router.delete("")
def cancel_plan(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    visit_plans.cancel_plan(session, customer=customer)
    return _state(session, workspace, customer)


@public_router.get(".ics")
def plan_calendar(
    k: str,
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> Response:
    """The plan as a calendar file ("Add to my calendar"), with a reminder 1 hour before. Opened
    as a link, so the customer's key comes in the address (like the Home Screen manifest)."""
    customer = customer_action.get_by_key(session, workspace_id=workspace.id, key=k[:80])
    plan = visit_plans.active_plan(session, customer=customer) if customer else None
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan to add")
    start, end = visit_plans.window(plan.day, plan.slot)
    _, _, label, hours = visit_plans.SLOTS[plan.slot]
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    url = f"{settings.PUBLIC_WEB_URL.rstrip('/')}/s/{workspace.slug}"

    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Customa//Visit plan//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:customa-plan-{plan.id}@customa",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
        f"DTEND:{end:%Y%m%dT%H%M%SZ}",
        f"SUMMARY:{esc(f'{label} at {workspace.name}')}",
        f"DESCRIPTION:{esc(f'My plan to come back ({hours}). A plan, not a booking. {url}')}",
        f"URL:{url}",
        "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(f'{label} at {workspace.name}')}", "TRIGGER:-PT1H", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="customa-plan.ics"', "Cache-Control": "no-store"},
    )


@cron_router.get("/plan-reminders")
def plan_reminders(
    authorization: str | None = Header(default=None),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Run by the scheduler every 15 minutes with "Authorization: Bearer <CRON_SECRET>".
    Idempotent: each reminder is claimed (reminder_sent_at) before it is sent."""
    secret = settings.CRON_SECRET
    if not secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not set")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Not allowed")
    return visit_plans.run_reminders(session, now=_now())
