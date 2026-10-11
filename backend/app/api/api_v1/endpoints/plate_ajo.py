"""Plate Ajo: prepaid plates at today's price. Customer routes (no login) and vendor routes
(stand members only). The rules live in app/services/plate_ajo.py."""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.actions import character_action, customer_action
from app.api import deps
from app.models import Customer, Workspace
from app.services import plate_ajo
from app.services.stands import resolve_stand_settings, set_stand_setting

public_router = APIRouter(prefix="/public/{workspace_slug}/ajo", tags=["plate_ajo"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/ajo", tags=["plate_ajo"])


class BundleRequest(BaseModel):
    item: str = Field(max_length=200)
    plates: int
    payer_name: str = Field(max_length=200)


class AjoSettingsRequest(BaseModel):
    enabled: bool
    bank_name: str | None = Field(default=None, max_length=200)
    account_number: str | None = Field(default=None, max_length=40)
    account_name: str | None = Field(default=None, max_length=200)


def ajo_customer_or_none(
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
    x_customer_key: str | None = Header(default=None),
) -> Customer | None:
    if not x_customer_key:
        return None
    return customer_action.get_by_key(session, workspace_id=workspace.id, key=x_customer_key)


def ajo_customer(customer: Customer | None = Depends(ajo_customer_or_none)) -> Customer:
    # Same answer as public.require_customer: the customer must have scanned here once.
    if customer is None:
        raise HTTPException(status_code=404, detail=plate_ajo.NOT_KNOWN)
    return customer


def _menu(session: Session, workspace: Workspace) -> list[dict[str, Any]]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    return list(character.menu or []) if character else []


# --- Customer ----------------------------------------------------------------------------------


@public_router.get("")
def read_ajo(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(ajo_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return plate_ajo.customer_state(
        session,
        workspace=workspace,
        customer=customer,
        stand_settings=resolve_stand_settings(session, workspace),
        menu=_menu(session, workspace),
    )


@public_router.post("/bundles")
def start_bundle(
    body: BundleRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(ajo_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    bundle = plate_ajo.create_bundle(
        session,
        workspace=workspace,
        customer=customer,
        stand_settings=resolve_stand_settings(session, workspace),
        menu=_menu(session, workspace),
        item=body.item,
        plates=body.plates,
        payer_name=body.payer_name,
    )
    return {"bundle": plate_ajo.bundle_view(bundle)}


@public_router.post("/use")
def use_prepaid_plate(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(ajo_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return plate_ajo.use_plate(
        session,
        workspace=workspace,
        customer=customer,
        stand_settings=resolve_stand_settings(session, workspace),
    )


# --- Vendor ------------------------------------------------------------------------------------


@vendor_router.get("")
def vendor_ajo(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return plate_ajo.vendor_state(
        session, workspace=workspace, stand_settings=resolve_stand_settings(session, workspace)
    )


@vendor_router.put("/settings")
def update_ajo_settings(
    body: AjoSettingsRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    values = plate_ajo.validate_settings(
        resolve_stand_settings(session, workspace),
        enabled=body.enabled,
        bank_name=body.bank_name,
        account_number=body.account_number,
        account_name=body.account_name,
    )
    for key, value in values.items():
        set_stand_setting(session, workspace, key, value)
    session.commit()
    return plate_ajo.vendor_state(
        session, workspace=workspace, stand_settings=resolve_stand_settings(session, workspace)
    )


@vendor_router.post("/bundles/{bundle_id}/confirm")
def confirm_bundle(
    bundle_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    bundle = plate_ajo.decide_bundle(
        session, workspace=workspace, bundle_id=bundle_id, confirm=True
    )
    return {"bundle": plate_ajo.bundle_view(bundle)}


@vendor_router.post("/bundles/{bundle_id}/reject")
def reject_bundle(
    bundle_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    bundle = plate_ajo.decide_bundle(
        session, workspace=workspace, bundle_id=bundle_id, confirm=False
    )
    return {"bundle": plate_ajo.bundle_view(bundle)}
