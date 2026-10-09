"""Customer routes: what a phone sees after scanning a stand's QR code.

No login. The stand is found from the slug in the URL (MSFLib workspace
lookup), and the customer is recognised by a random key their phone keeps and
sends back in the X-Customer-Key header.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.actions import (
    PlateTooSoon,
    character_action,
    customer_action,
    jara_action,
    rating_action,
    visit_action,
)
from app.api import deps
from app.models import Customer, CustomerCreate, JaraReward, Rating, RatingCreate, Visit, Workspace
from app.services.bisi import chat_reply
from app.services.stands import resolve_stand_settings

router = APIRouter(prefix="/public/{workspace_slug}", tags=["customer"])


class CountPlateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=40)
    consent: bool = False


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class RateRequest(BaseModel):
    visit_id: int
    stars: int = Field(ge=1, le=5)


def get_customer_or_none(
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
    x_customer_key: str | None = Header(default=None),
) -> Customer | None:
    if not x_customer_key:
        return None
    return customer_action.get_by_key(session, workspace_id=workspace.id, key=x_customer_key)


def require_customer(customer: Customer | None = Depends(get_customer_or_none)) -> Customer:
    if customer is None:
        raise HTTPException(status_code=404, detail="We don't know you at this stand yet")
    return customer


def customer_view(customer: Customer, last: Visit | None) -> dict[str, Any]:
    return {
        "key": customer.key,
        "first_name": customer.first_name,
        "plate_number": last.plate_number if last else 0,
    }


@router.get("")
def read_stand(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    stand_settings = resolve_stand_settings(session, workspace)
    last = visit_action.last_for_customer(session, customer_id=customer.id) if customer else None
    return {
        "stand": {"name": workspace.name, "slug": workspace.slug, "description": workspace.description},
        "character": character.model_dump(exclude={"workspace_id"}) if character else None,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "window_seconds": stand_settings.PLATE_WINDOW_SECONDS,
        "customer": customer_view(customer, last) if customer else None,
    }


@router.post("/visits")
def count_plate(
    body: CountPlateRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    returning = customer is not None
    if customer is None:
        # We only keep a name when the customer agreed to it.
        first_name = body.first_name.strip() if body.consent and body.first_name else None
        customer = customer_action.create_for_stand(
            session,
            workspace_id=workspace.id,
            data=CustomerCreate(first_name=first_name, consent=body.consent),
        )

    stand_settings = resolve_stand_settings(session, workspace)
    try:
        visit = visit_action.count_plate(
            session,
            workspace_id=workspace.id,
            customer_id=customer.id,
            window_seconds=stand_settings.PLATE_WINDOW_SECONDS,
            plates_for_jara=stand_settings.PLATES_FOR_JARA,
        )
    except PlateTooSoon as exc:
        last = visit_action.last_for_customer(session, customer_id=customer.id)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This plate is already counted",
                "seconds_left": exc.seconds_left,
                "customer": customer_view(customer, last),
            },
        )

    jara = jara_action.get_by_all(session, visit_id=visit.id)
    return {
        "customer": customer_view(customer, visit),
        "returning": returning,
        "visit_id": visit.id,
        "plate_number": visit.plate_number,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "jara": {"code": jara.code} if jara else None,
    }


@router.post("/ratings")
def rate_plate(
    body: RateRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    visit = visit_action.get_by_all(
        session, id=body.visit_id, customer_id=customer.id, workspace_id=workspace.id
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    existing = rating_action.get_by_all(session, visit_id=visit.id)
    if existing:
        rating_action.update(session, model=existing, update={"stars": body.stars})
    else:
        rating_action.create(
            session,
            data=RatingCreate(stars=body.stars),
            update={"workspace_id": workspace.id, "customer_id": customer.id, "visit_id": visit.id},
        )
    return {"ok": True, "stars": body.stars}


@router.delete("/me")
def delete_my_data(
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Forget this customer at this stand: ratings, jara, plates, then the customer."""
    for model, action in ((Rating, rating_action), (JaraReward, jara_action), (Visit, visit_action)):
        action.delete_multi_by_expressions(session, model.customer_id == customer.id)
    customer_action.delete(session, customer.id)
    return {"deleted": True}


@router.post("/chat")
def chat(
    body: ChatRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Talk to the stand's character (MSFLib ai-core, with a no-AI fallback)."""
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    if character is None:
        raise HTTPException(status_code=404, detail="This stand has no character yet")
    last = visit_action.last_for_customer(session, customer_id=customer.id) if customer else None
    reply, source = chat_reply(
        character=character,
        stand_name=workspace.name,
        customer_name=customer.first_name if customer else None,
        plate=last.plate_number if last else 0,
        total=resolve_stand_settings(session, workspace).PLATES_FOR_JARA,
        message=body.message,
        history=body.history,
        workspace_id=workspace.id,
    )
    return {"reply": reply, "source": source}
