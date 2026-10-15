"""Customer delights, vendor side: surprise jara and today's special (stand members only).

Both are per-stand tiered settings. Customers meet them through the plate count (a surprise
jara) and the chat (the character announces today's special).
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api import deps
from app.core.config import CustomaSettings
from app.models import Workspace
from app.services.character_chat import today_in_nigeria, todays_special
from app.services.stands import resolve_stand_settings, set_stand_setting

vendor_router = APIRouter(prefix="/stands/{workspace_slug}/delights", tags=["delights"])


class SurpriseRequest(BaseModel):
    enabled: bool


class SpecialRequest(BaseModel):
    # Empty text clears today's special.
    text: str = Field(default="", max_length=80)


def _view(stand_settings: CustomaSettings) -> dict[str, Any]:
    return {
        "surprise_enabled": stand_settings.SURPRISE_JARA_ENABLED,
        "surprise_one_in": stand_settings.SURPRISE_JARA_ONE_IN,
        "special": todays_special(stand_settings),
    }


@vendor_router.get("")
def read_delights(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    return _view(resolve_stand_settings(session, workspace))


@vendor_router.put("/surprise")
def update_surprise(
    body: SurpriseRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Turn surprise jara on or off."""
    set_stand_setting(session, workspace, "SURPRISE_JARA_ENABLED", body.enabled)
    session.commit()
    return _view(resolve_stand_settings(session, workspace))


@vendor_router.put("/special")
def update_special(
    body: SpecialRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Set today's special (it shows until midnight, Nigeria time). Empty text clears it."""
    text = body.text.strip()
    set_stand_setting(session, workspace, "TODAYS_SPECIAL", text or None)
    set_stand_setting(session, workspace, "TODAYS_SPECIAL_DATE", today_in_nigeria().isoformat() if text else None)
    session.commit()
    return _view(resolve_stand_settings(session, workspace))
