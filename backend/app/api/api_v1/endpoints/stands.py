"""Vendor routes: create a stand, see the live dashboard, edit the character.

Sign-in comes from MSFLib auth (bearer token). Dashboard routes carry the
stand's slug, and MSFLib's workspace dependencies check the vendor is a member.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from app.actions import character_action, workspace_action
from app.api import deps
from app.models import (
    Account,
    CharacterCreate,
    CharacterUpdate,
    Customer,
    JaraReward,
    Rating,
    Visit,
    Workspace,
)
from app.services.bisi import suggest_character
from app.services.stands import create_stand, resolve_stand_settings

router = APIRouter(prefix="/stands", tags=["stands"])


class StandCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=200)
    character: CharacterCreate


def stand_view(session: Session, workspace: Workspace) -> dict[str, Any]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    return {
        "name": workspace.name,
        "slug": workspace.slug,
        "description": workspace.description,
        "character": character.model_dump(exclude={"workspace_id"}) if character else None,
    }


@router.post("", status_code=201)
def create_my_stand(
    body: StandCreateRequest,
    account: Account = Depends(deps.get_current_active_account),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    try:
        workspace, _ = create_stand(
            session,
            owner=account,
            name=body.name,
            description=body.description or body.name,
            character=body.character,
        )
    except Exception as exc:  # most often a slug already taken
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Could not create this stand: {exc}")
    return stand_view(session, workspace)


class SuggestRequest(BaseModel):
    description: str = Field(min_length=3, max_length=300)


@router.post("/suggest-character")
def suggest(
    body: SuggestRequest,
    _account: Account = Depends(deps.get_current_active_account),
) -> dict[str, Any]:
    """A character from the vendor's own words: AI output checked by a Pydantic schema."""
    suggestion, source = suggest_character(body.description)
    return {**suggestion.model_dump(), "source": source}


@router.get("/mine")
def my_stands(
    account: Account = Depends(deps.get_current_active_account),
    session: Session = Depends(deps.get_session),
) -> list[dict[str, Any]]:
    stands = workspace_action.get_multi_by_all(session, owner_id=account.id, limit=None)
    return [stand_view(session, ws) for ws in stands if not ws.is_default]


@router.get("/{workspace_slug}/dashboard")
def dashboard(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    ws = workspace.id
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    def count(stmt) -> int:
        return session.exec(stmt).one()

    plates_today = count(
        select(func.count(Visit.id)).where(Visit.workspace_id == ws, Visit.created_at >= today)
    )
    customers = count(select(func.count(Customer.id)).where(Customer.workspace_id == ws))
    returning = count(
        select(func.count(func.distinct(Visit.customer_id))).where(
            Visit.workspace_id == ws, Visit.plate_number > 1
        )
    )
    jara_issued = count(select(func.count(JaraReward.id)).where(JaraReward.workspace_id == ws))
    avg_stars = session.exec(select(func.avg(Rating.stars)).where(Rating.workspace_id == ws)).one()

    recent = session.exec(
        select(Visit, Customer, Rating)
        .join(Customer, Customer.id == Visit.customer_id)
        .join(Rating, Rating.visit_id == Visit.id, isouter=True)
        .where(Visit.workspace_id == ws)
        .order_by(Visit.id.desc())
        .limit(20)
    ).all()

    return {
        "stand": stand_view(session, workspace),
        "plates_for_jara": resolve_stand_settings(session, workspace).PLATES_FOR_JARA,
        "stats": {
            "plates_today": plates_today,
            "customers": customers,
            "returning_customers": returning,
            "jara_issued": jara_issued,
            "average_rating": round(float(avg_stars), 1) if avg_stars is not None else None,
        },
        "recent_visits": [
            {
                "id": visit.id,
                "name": customer.first_name or "Guest",
                "plate_number": visit.plate_number,
                "stars": rating.stars if rating else None,
                "at": visit.created_at,
            }
            for visit, customer, rating in recent
        ],
    }


@router.put("/{workspace_slug}/character")
def update_character(
    body: CharacterUpdate,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    if character is None:
        raise HTTPException(status_code=404, detail="This stand has no character yet")
    character_action.update(session, model=character, data=body)
    return stand_view(session, workspace)
