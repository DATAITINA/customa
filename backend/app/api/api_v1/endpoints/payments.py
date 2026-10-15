"""Pay for a plate: customer routes (no login, the customer's key), vendor routes (stand members)
and the Paystack webhook. The rules live in app/services/payments.py."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.actions import character_action
from app.actions.payments import payment_action
from app.api import deps
from app.api.api_v1.endpoints.public import get_customer_or_none, require_customer
from app.models import Account, Customer, Workspace
from app.services import payments, paystack
from app.services.payments import PaymentError
from app.services.stands import resolve_stand_settings, set_stand_setting

public_router = APIRouter(prefix="/public/{workspace_slug}/pay", tags=["payments"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/payments", tags=["payments"])
webhook_router = APIRouter(prefix="/payments", tags=["payments"])


class StartRequest(BaseModel):
    item: str = Field(min_length=1, max_length=200)
    method: str = Field(pattern="^(paystack|cash)$")


class ConfirmRequest(BaseModel):
    reference: str = Field(min_length=6, max_length=80)


class SettingsRequest(BaseModel):
    enabled: bool


def _fail(exc: PaymentError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.message)


@public_router.get("")
def pay_state(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return payments.customer_state(
        session, workspace=workspace, customer=customer,
        character=character_action.get_for_stand(session, workspace_id=workspace.id),
        stand_settings=resolve_stand_settings(session, workspace),
    )


@public_router.post("")
def start_payment(
    body: StartRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        return payments.start(
            session, workspace=workspace, customer=customer,
            character=character_action.get_for_stand(session, workspace_id=workspace.id),
            stand_settings=resolve_stand_settings(session, workspace), item=body.item, method=body.method,
        )
    except PaymentError as exc:
        raise _fail(exc)


@public_router.post("/confirm")
def confirm_payment(
    body: ConfirmRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """The Paystack return page: did the payment go through? (Paystack is asked, never trusted
    from the URL.)"""
    try:
        p = payments.confirm_paystack(
            session, workspace=workspace, reference=body.reference,
            stand_settings=resolve_stand_settings(session, workspace),
        )
    except PaymentError as exc:
        raise _fail(exc)
    return {"payment": payments.view(p)}


@public_router.delete("/{payment_id}")
def cancel_my_payment(
    payment_id: int,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        payments.cancel(session, workspace=workspace, payment_id=payment_id, customer=customer)
    except PaymentError as exc:
        raise _fail(exc)
    return {"cancelled": True}


# --- Vendor ------------------------------------------------------------------------------


@vendor_router.get("/today")
def payments_today(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    stand_settings = resolve_stand_settings(session, workspace)
    return {"enabled": payments.enabled(stand_settings), **payments.today(session, workspace=workspace)}


@vendor_router.put("/settings")
def payment_settings(
    body: SettingsRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    set_stand_setting(session, workspace, "PAYMENTS_ENABLED", body.enabled)
    session.commit()
    return {"enabled": body.enabled, **payments.today(session, workspace=workspace)}


@vendor_router.post("/{payment_id}/cash-received")
def cash_received(
    payment_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    account: Account = Depends(deps.get_current_active_account),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        p = payments.confirm_cash(
            session, workspace=workspace, payment_id=payment_id, account_id=account.id,
            stand_settings=resolve_stand_settings(session, workspace),
        )
    except PaymentError as exc:
        raise _fail(exc)
    return {"payment": payments.view(p)}


@vendor_router.post("/{payment_id}/cancel")
def vendor_cancel(
    payment_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        payments.cancel(session, workspace=workspace, payment_id=payment_id)
    except PaymentError as exc:
        raise _fail(exc)
    return {"cancelled": True}


# --- Paystack webhook ----------------------------------------------------------------------


@webhook_router.post("/paystack/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Paystack calls this when a charge succeeds. Signed with our test key (HMAC-SHA512);
    unsigned or wrongly signed calls are refused. The payment is then re-checked with Paystack."""
    raw = await request.body()
    if not paystack.signature_ok(raw, x_paystack_signature):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad body")
    if event.get("event") != "charge.success":
        return {"ok": True}
    reference = str((event.get("data") or {}).get("reference") or "")
    p = payment_action.by_reference(session, reference=reference)
    if p is None:
        return {"ok": True}  # not one of ours
    workspace = session.get(Workspace, p.workspace_id)
    try:
        payments.confirm_paystack(
            session, workspace=workspace, reference=reference,
            stand_settings=resolve_stand_settings(session, workspace),
        )
    except PaymentError:
        pass  # the amount check or Paystack itself said no: nothing to stamp
    return {"ok": True}
