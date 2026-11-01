"""Regular-arrived alert: staff routes ("Greeted", phone pings) and the customer's own "my usual"
(no login, the customer's key). "Who's here now" itself comes with the dashboard (stands.py).
Rules: app/services/regulars.py."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.actions import character_action
from app.api import deps
from app.api.api_v1.endpoints.public import require_customer
from app.core.config import settings
from app.models import Account, Customer, Workspace
from app.services import alerts, regulars
from app.services.regulars import RegularsError

vendor_router = APIRouter(prefix="/stands/{workspace_slug}/arrivals", tags=["regulars"])
public_router = APIRouter(prefix="/public/{workspace_slug}/usual", tags=["regulars"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


class UsualRequest(BaseModel):
    item: str = Field(min_length=1, max_length=200)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@vendor_router.post("/{arrival_id}/greeted")
def greeted(
    arrival_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Staff greeted this customer in person (saved, to measure greeting)."""
    try:
        arrival = regulars.mark_greeted(session, workspace=workspace, arrival_id=arrival_id, now=_now())
    except RegularsError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return {"id": arrival.id, "greeted_at": arrival.greeted_at}


@vendor_router.get("/ping")
def ping_info(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Whether "Ping me when regulars arrive" can be turned on (the key the browser needs)."""
    available = alerts.alerts_available()
    return {
        "available": available,
        "public_key": settings.VAPID_PUBLIC_KEY if available else None,
        "phones": regulars.vendor_phones(session, workspace=workspace),
    }


@vendor_router.post("/ping")
def ping_on(
    body: SubscribeRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    account: Account = Depends(deps.get_current_active_account),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        regulars.vendor_subscribe(
            session, workspace=workspace, account_id=account.id,
            endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth,
        )
    except RegularsError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return {"subscribed": True}


@vendor_router.post("/ping/off")
def ping_off(
    body: UnsubscribeRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    regulars.vendor_unsubscribe(session, workspace=workspace, endpoint=body.endpoint)
    return {"subscribed": False}


# --- Customer: "Let <stand> know my usual" (off until they turn it on) ---------------------


@public_router.get("")
def read_usual(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    return {"usual": regulars.get_usual(session, customer=customer), "menu": regulars.menu_items(character)}


@public_router.put("")
def set_usual(
    body: UsualRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    try:
        item = regulars.set_usual(session, workspace=workspace, customer=customer, character=character, item=body.item)
    except RegularsError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    return {"usual": item}


@public_router.delete("")
def clear_usual(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    regulars.clear_usual(session, customer=customer)
    return {"usual": None}
