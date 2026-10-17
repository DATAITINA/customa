"""Save your card / "Already have a card?": customer routes (no login). The rules live in
app/services/card_recovery.py."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.actions import visit_action
from app.api import deps
from app.api.api_v1.endpoints.public import customer_view, get_customer_or_none, require_customer
from app.models import Customer, Workspace
from app.services import card_recovery
from app.services.card_recovery import RecoveryError
from app.services.stands import resolve_stand_settings

router = APIRouter(prefix="/public/{workspace_slug}/card", tags=["card_recovery"])


class LinkRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=24)
    pin: str = Field(min_length=4, max_length=4)


class CodeRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=24)


class RecoverRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=24)
    pin: str | None = Field(default=None, max_length=4)
    code: str | None = Field(default=None, max_length=6)


def client_ip(request: Request) -> str | None:
    """The caller's address (Vercel puts it first in X-Forwarded-For). Only its hash is kept."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _fail(exc: RecoveryError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.message)


@router.get("")
def card_state(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return card_recovery.state(session, customer=customer, stand_settings=resolve_stand_settings(session, workspace))


@router.put("/phone")
def link_phone(
    body: LinkRequest,
    request: Request,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        return card_recovery.link(
            session, workspace=workspace, customer=customer, stand_settings=resolve_stand_settings(session, workspace),
            phone_raw=body.phone, pin=body.pin, ip=client_ip(request),
        )
    except RecoveryError as exc:
        raise _fail(exc)


@router.delete("/phone")
def unlink_phone(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return card_recovery.unlink(session, customer=customer, stand_settings=resolve_stand_settings(session, workspace))


@router.post("/recover/code")
def send_code(
    body: CodeRequest,
    request: Request,
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        return card_recovery.send_code(
            session, workspace=workspace, stand_settings=resolve_stand_settings(session, workspace),
            phone_raw=body.phone, ip=client_ip(request),
        )
    except RecoveryError as exc:
        raise _fail(exc)


@router.post("/recover")
def recover(
    body: RecoverRequest,
    request: Request,
    workspace: Workspace = Depends(deps.get_stand_public),
    current: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Proves the card is the caller's (PIN or SMS code). Returns a fresh key for this browser
    and the card, with every plate, jara, crew card, plan and prize intact."""
    if not body.pin and not body.code:
        raise HTTPException(status_code=400, detail="Enter your 4-digit PIN or the code we texted you.")
    stand_settings = resolve_stand_settings(session, workspace)
    try:
        customer, key = card_recovery.recover(
            session, workspace=workspace, stand_settings=stand_settings, phone_raw=body.phone,
            pin=body.pin, code=body.code, current=current, ip=client_ip(request),
        )
    except RecoveryError as exc:
        raise _fail(exc)
    last = visit_action.last_for_customer(session, customer_id=customer.id)
    return {"key": key, "customer": customer_view(customer, last, stand_settings, session)}
