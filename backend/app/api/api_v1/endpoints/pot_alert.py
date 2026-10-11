"""Pot Alert: tell me when my dish is ready.

Customer routes (no login, X-Customer-Key) and vendor routes (stand members only). Phone numbers
leave the server only on vendor routes; a customer sees their own number masked.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.api.api_v1.endpoints.public import get_customer_or_none, require_customer
from app.models import Customer, Workspace
from app.services import pot_alert
from app.services.pot_alert import MAX_PLATES_LEFT, PotAlertError
from app.services.stands import resolve_stand_settings, set_stand_setting

public_router = APIRouter(prefix="/public/{workspace_slug}/pot", tags=["pot_alert"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/pot", tags=["pot_alert"])


def is_enabled(session: Session, workspace: Workspace) -> bool:
    return bool(resolve_stand_settings(session, workspace).POT_ALERT_ENABLED)


def require_enabled(session: Session, workspace: Workspace) -> None:
    if not is_enabled(session, workspace):
        raise HTTPException(status_code=404, detail="Pot Alert is not on at this stand")


def bad_request(exc: PotAlertError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Customer --------------------------------------------------------------------------------


class WatchRequest(BaseModel):
    # Counts, menu names and the phone are checked by the service, for clear 400 messages.
    items: list[str] = Field(default_factory=list, max_length=50)
    # Empty keeps the number already saved (the customer only ever sees it masked).
    phone: str = Field(default="", max_length=40)
    # The customer agrees the vendor may message them on WhatsApp. Required on every save.
    consent: bool = False


@public_router.get("")
def read_pot(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return pot_alert.public_view(
        session, workspace=workspace, customer=customer, enabled=is_enabled(session, workspace)
    )


@public_router.put("/watches")
def save_watches(
    body: WatchRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    require_enabled(session, workspace)
    try:
        pot_alert.set_watches(
            session,
            workspace=workspace,
            customer=customer,
            items=body.items,
            phone=body.phone,
            consent=body.consent,
        )
    except PotAlertError as exc:
        raise bad_request(exc)
    return {"my": pot_alert.my_watch(session, workspace=workspace, customer=customer)}


@public_router.delete("/watches")
def delete_watches(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    # Allowed even when the feature is off: a customer can always remove their number.
    pot_alert.clear_watches(session, workspace=workspace, customer=customer)
    return {"my": None}


# --- Vendor ----------------------------------------------------------------------------------


class SettingsRequest(BaseModel):
    enabled: bool


class ReadyRequest(BaseModel):
    item: str = Field(min_length=1, max_length=120)
    plates_left: int | None = Field(default=None, ge=1, le=MAX_PLATES_LEFT)


def ready_or_404(session: Session, workspace: Workspace, ready_id: int):
    ready = pot_alert.get_ready(session, workspace=workspace, ready_id=ready_id)
    if ready is None:
        raise HTTPException(status_code=404, detail="No such ready call at this stand")
    return ready


@vendor_router.get("")
def vendor_pot(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return pot_alert.vendor_view(
        session, workspace=workspace, enabled=is_enabled(session, workspace)
    )


@vendor_router.put("/settings")
def update_settings(
    body: SettingsRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    set_stand_setting(session, workspace, "POT_ALERT_ENABLED", body.enabled)
    session.commit()
    return pot_alert.vendor_view(
        session, workspace=workspace, enabled=is_enabled(session, workspace)
    )


@vendor_router.post("/ready")
def ready_now(
    body: ReadyRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    require_enabled(session, workspace)
    try:
        ready = pot_alert.mark_ready(
            session, workspace=workspace, item=body.item, plates_left=body.plates_left
        )
    except PotAlertError as exc:
        raise bad_request(exc)
    return {
        "ready": pot_alert.ready_view(ready),
        "watchers": pot_alert.watchers_for(session, workspace=workspace, item=ready.item),
    }


@vendor_router.get("/ready/{ready_id}/watchers")
def ready_watchers(
    ready_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    ready = ready_or_404(session, workspace, ready_id)
    return {
        "ready": pot_alert.ready_view(ready),
        "watchers": pot_alert.watchers_for(session, workspace=workspace, item=ready.item),
    }


@vendor_router.post("/ready/{ready_id}/end")
def end_ready(
    ready_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    ready = pot_alert.end_ready(session, ready=ready_or_404(session, workspace, ready_id))
    return {"ready": pot_alert.ready_view(ready), "ended": ready.ended}
