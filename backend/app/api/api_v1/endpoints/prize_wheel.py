"""Prize Wheel: the vendor's wheel of food prizes (stand members only), the customer's spin
(no login, the customer's key), and the vendor's jara code check. Rules: app/services/prize_wheel.py.
"""

import base64
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.api.api_v1.endpoints.public import get_customer_or_none, require_customer
from app.models import Customer, Workspace
from app.services import prize_wheel
from app.services.prize_wheel import WheelError
from app.services.stands import resolve_stand_settings

public_router = APIRouter(prefix="/public/{workspace_slug}/wheel", tags=["prize_wheel"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}", tags=["prize_wheel"])

Weight = Literal[1, 3, 5]


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=200)
    prize: str | None = Field(default=None, max_length=100)
    weight: Weight = 3
    available: bool = True
    photo: str | None = Field(default=None, max_length=1_000_000)  # data URL, shrunk on the phone


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=200)
    prize: str | None = Field(default=None, max_length=100)
    weight: Weight | None = None
    available: bool | None = None
    # A data URL replaces the photo; null removes it; leave it out to keep it.
    photo: str | None = Field(default=None, max_length=1_000_000)


class PublishRequest(BaseModel):
    enabled: bool


class SpinRequest(BaseModel):
    jara_id: int


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fail(exc: WheelError):
    raise HTTPException(status_code=exc.status, detail=exc.message)


# --- Customer --------------------------------------------------------------------------------


@public_router.get("")
def read_wheel(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """The wheel's prizes, and this customer's spins waiting and prizes won."""
    return prize_wheel.customer_state(
        session, workspace=workspace, customer=customer, stand_settings=resolve_stand_settings(session, workspace)
    )


@public_router.post("/spin")
def spin(
    body: SpinRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Spin with one of the customer's jara. The server picks the prize and where the wheel
    stops; the phone animates exactly that. Asking again returns the same result."""
    try:
        return prize_wheel.spin(
            session, workspace=workspace, customer=customer, jara_id=body.jara_id,
            stand_settings=resolve_stand_settings(session, workspace), now=_now(),
        )
    except WheelError as exc:
        _fail(exc)


@public_router.get("/items/{item_id}/photo")
def item_photo(
    item_id: int,
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> Response:
    item = session.get(prize_wheel.WheelItem, item_id)
    if item is None or item.workspace_id != workspace.id or not item.photo_data:
        raise HTTPException(status_code=404, detail="No photo")
    # The URL carries the photo's version, so a new photo gets a new URL: cache for good.
    return Response(
        content=base64.b64decode(item.photo_data),
        media_type=item.photo_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# --- Vendor ----------------------------------------------------------------------------------


def _vendor_view(session: Session, workspace: Workspace) -> dict[str, Any]:
    return prize_wheel.vendor_view(session, workspace, resolve_stand_settings(session, workspace))


@vendor_router.get("/wheel")
def vendor_wheel(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return _vendor_view(session, workspace)


@vendor_router.post("/wheel/items")
def add_item(
    body: ItemCreate,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        prize_wheel.add_item(session, workspace, body.model_dump())
    except WheelError as exc:
        _fail(exc)
    return _vendor_view(session, workspace)


@vendor_router.put("/wheel/items/{item_id}")
def update_item(
    item_id: int,
    body: ItemUpdate,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        prize_wheel.update_item(session, workspace, item_id, body.model_dump(exclude_unset=True))
    except WheelError as exc:
        _fail(exc)
    return _vendor_view(session, workspace)


@vendor_router.delete("/wheel/items/{item_id}")
def delete_item(
    item_id: int,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        prize_wheel.delete_item(session, workspace, item_id)
    except WheelError as exc:
        _fail(exc)
    return _vendor_view(session, workspace)


@vendor_router.put("/wheel")
def publish_wheel(
    body: PublishRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        prize_wheel.publish(session, workspace, body.enabled)
    except WheelError as exc:
        _fail(exc)
    return _vendor_view(session, workspace)


@vendor_router.get("/jara/{code}")
def check_jara(
    code: str,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Check a jara code the customer shows (typed or scanned): what it is worth, and whether
    it can be given (valid), was given already, expired, is not spun yet, or is another stand's."""
    stand_settings = resolve_stand_settings(session, workspace)
    return prize_wheel.check_code(
        session, workspace=workspace, code=code[:40], now=_now(),
        wheel_live=prize_wheel.is_live(session, workspace, stand_settings),
    )
