"""Leftover-food alerts, customer side: turn this stand's push alerts or text-message alerts on
or off (no login, the customer's key). The vendor sends them with "Tell my customers"
(stands.py, last-plates)."""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.api.api_v1.endpoints.public import get_customer_or_none, require_customer
from app.core.config import settings
from app.models import Customer, Workspace
from app.services import alerts, sms_alerts
from app.services.alerts import AlertError
from app.services.sms_alerts import SmsError
from app.services.stands import resolve_stand_settings

public_router = APIRouter(prefix="/public/{workspace_slug}/alerts", tags=["alerts"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


class SmsRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=24)
    # The customer ticked "I agree" to the terms the page showed (sms_alerts.TERMS).
    agree: Literal[True]


@public_router.get("")
def read_alerts(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Which alerts can be turned on: push (with the key the browser needs to subscribe) and text
    messages (with the terms to agree to, and this customer's number, masked, if texts are on)."""
    available = alerts.alerts_available()
    sms = sms_alerts.sms_available()
    row = sms_alerts.number_for(session, workspace=workspace, customer=customer) if sms and customer else None
    return {
        "available": available,
        "public_key": settings.VAPID_PUBLIC_KEY if available else None,
        "sms": sms,
        "sms_terms": sms_alerts.terms_text(workspace) if sms else None,
        "texting": sms_alerts.masked(row.phone) if row else None,
    }


@public_router.post("/sms")
def turn_on_texts(
    body: SmsRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        row = sms_alerts.subscribe(
            session, workspace=workspace, customer=customer, phone=body.phone,
            stand_settings=resolve_stand_settings(session, workspace), now=datetime.now(UTC).replace(tzinfo=None),
        )
    except SmsError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"texting": sms_alerts.masked(row.phone)}


@public_router.post("/sms/off")
def turn_off_texts(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    sms_alerts.unsubscribe(session, workspace=workspace, customer=customer)
    return {"texting": None}


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
