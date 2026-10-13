"""Leftover-food alerts, customer side: turn this stand's push alerts on or off (no login,
the customer's key). The vendor sends them with "Tell my customers" (stands.py, last-plates)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.api.api_v1.endpoints.public import require_customer
from app.core.config import settings
from app.models import Customer, Workspace
from app.services import alerts
from app.services.alerts import AlertError

public_router = APIRouter(prefix="/public/{workspace_slug}/alerts", tags=["alerts"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


@public_router.get("")
def read_alerts(workspace: Workspace = Depends(deps.get_stand_public)) -> dict[str, Any]:
    """Whether alerts can be turned on, and the key the browser needs to subscribe."""
    available = alerts.alerts_available()
    return {"available": available, "public_key": settings.VAPID_PUBLIC_KEY if available else None}


@public_router.post("")
def turn_on(
    body: SubscribeRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        alerts.subscribe(
            session, workspace=workspace, customer=customer,
            endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth,
        )
    except AlertError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"subscribed": True}


@public_router.post("/off")
def turn_off(
    body: UnsubscribeRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    alerts.unsubscribe(session, workspace=workspace, customer=customer, endpoint=body.endpoint)
    return {"subscribed": False}
