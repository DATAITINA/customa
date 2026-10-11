"""Lunch Crew: a shared card with ajo rotation for jara. Customer routes (no login) and vendor routes (stand members only)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.api.api_v1.endpoints.public import get_customer_or_none, require_customer
from app.models import Customer, Workspace
from app.services import lunch_crew
from app.services.lunch_crew import CrewError
from app.services.stands import resolve_stand_settings, set_stand_setting

public_router = APIRouter(prefix="/public/{workspace_slug}/crew", tags=["lunch_crew"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/crew", tags=["lunch_crew"])


class CreateCrewRequest(BaseModel):
    name: str = Field(min_length=lunch_crew.NAME_MIN, max_length=lunch_crew.NAME_MAX)


class JoinCrewRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class CrewSettingsRequest(BaseModel):
    enabled: bool


def _http(exc: CrewError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _state(
    session: Session, workspace: Workspace, customer: Customer | None, code: str | None = None
) -> dict[str, Any]:
    return lunch_crew.public_state(
        session,
        workspace=workspace,
        customer=customer,
        code=code,
        stand_settings=resolve_stand_settings(session, workspace),
    )


# --- Customer --------------------------------------------------------------------------------


@public_router.get("")
def read_crew(
    code: str | None = None,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """My crew (if any), and the crew behind an invite code from a share link (?code=)."""
    return _state(session, workspace, customer, code)


@public_router.post("")
def create_crew(
    body: CreateCrewRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        lunch_crew.create_crew(
            session,
            workspace=workspace,
            customer=customer,
            name=body.name,
            stand_settings=resolve_stand_settings(session, workspace),
        )
    except CrewError as exc:
        raise _http(exc)
    return _state(session, workspace, customer)


@public_router.post("/join")
def join_crew(
    body: JoinCrewRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        lunch_crew.join_crew(
            session,
            workspace=workspace,
            customer=customer,
            code=body.code,
            stand_settings=resolve_stand_settings(session, workspace),
        )
    except CrewError as exc:
        raise _http(exc)
    return _state(session, workspace, customer)


@public_router.post("/leave")
def leave_crew(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        lunch_crew.leave_crew(session, workspace=workspace, customer=customer)
    except CrewError as exc:
        raise _http(exc)
    return _state(session, workspace, customer)


# --- Vendor ----------------------------------------------------------------------------------


@vendor_router.get("")
def vendor_crews(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Every crew at this stand, with members in join order and whose jara is next."""
    return lunch_crew.vendor_state(
        session, workspace=workspace, stand_settings=resolve_stand_settings(session, workspace)
    )


@vendor_router.put("/settings")
def update_crew_settings(
    body: CrewSettingsRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Turn Lunch Crew on or off. Off: crews are kept, but every plate counts on the
    customer's own card and customers do not see crews."""
    set_stand_setting(session, workspace, "LUNCH_CREW_ENABLED", body.enabled)
    session.commit()
    return lunch_crew.vendor_state(
        session, workspace=workspace, stand_settings=resolve_stand_settings(session, workspace)
    )
