"""Customer routes: what a phone sees after scanning a stand's QR code.

No login. The stand is found from the slug in the URL (MSFLib workspace
lookup), and the customer is recognised by a random key their phone keeps and
sends back in the X-Customer-Key header.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import object_session
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
from app.core.config import CustomaSettings
from app.models import Customer, CustomerCreate, JaraReward, Rating, RatingCreate, Visit, Workspace
from app.services import lunch_crew, plate_ajo, pot_alert
from app.services.bisi import chat_reply
from app.services.chat_log import forget_customer, record_turn
from app.services.plates import count_visit
from app.services.stands import last_plates, resolve_stand_settings

router = APIRouter(prefix="/public/{workspace_slug}", tags=["customer"])


class CountPlateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=40)
    consent: bool = False
    # "qr" when the page was opened from the stand's QR code. Saved once, when the
    # customer is first created, so the vendor can see how customers arrive.
    source: str | None = Field(default=None, max_length=20)


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


def window_seconds_for(customer: Customer, stand_settings: CustomaSettings) -> int:
    """The wait between plates, decided on the server: the stand's window for every customer."""
    return stand_settings.PLATE_WINDOW_SECONDS


def customer_view(
    customer: Customer,
    last: Visit | None,
    stand_settings: CustomaSettings,
    session: Session | None = None,
) -> dict[str, Any]:
    """What the phone shows about this customer.

    plate_number is the last plate on the card their plates go to now: the crew card when
    Lunch Crew is on and they are in a crew (crew_name is then set), else their own card (crew
    plates never count there). `last` is their last plate of any kind (for seconds_left).
    open_jara lists their unredeemed jara codes at this stand, so a code is never lost.
    own_plate_number: plates on their own card toward its next jara (0..N-1); while they are
    in a crew this is where the own card is paused.
    """
    session = session or object_session(customer)
    plate_number = last.plate_number if last else 0
    own_plate_number = plate_number % stand_settings.PLATES_FOR_JARA
    crew_name = None
    open_jara: list[dict[str, str]] = []
    if session is not None:
        own = visit_action.last_own_card_visit(session, customer_id=customer.id)
        plate_number = own.plate_number if own else 0
        own_plate_number = plate_number % stand_settings.PLATES_FOR_JARA
        card = lunch_crew.card_for_customer(
            session,
            workspace_id=customer.workspace_id,
            customer_id=customer.id,
            stand_settings=stand_settings,
        )
        if card is not None:
            crew_name, plate_number = card
        open_jara = [
            {"code": j.code}
            for j in jara_action.open_for_customer(
                session, workspace_id=customer.workspace_id, customer_id=customer.id
            )
        ]
    return {
        "key": customer.key,
        "first_name": customer.first_name,
        "plate_number": plate_number,
        "window_seconds": window_seconds_for(customer, stand_settings),
        "seconds_left": seconds_left(last, stand_settings),
        "crew_name": crew_name,
        "own_plate_number": own_plate_number,
        "open_jara": open_jara,
    }


def seconds_left(last: Visit | None, stand_settings: CustomaSettings) -> int:
    """Seconds until this customer's next plate can count (0 = it can count now). Read only."""
    if last is None:
        return 0
    next_allowed = last.created_at + timedelta(seconds=stand_settings.PLATE_WINDOW_SECONDS)
    return max(0, int((next_allowed - datetime.now(UTC).replace(tzinfo=None)).total_seconds()))


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
        "last_plates": last_plates(stand_settings),
        "customer": customer_view(customer, last, stand_settings, session) if customer else None,
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
            data=CustomerCreate(
                first_name=first_name,
                consent=body.consent,
                source="qr" if body.source == "qr" else None,
            ),
        )

    stand_settings = resolve_stand_settings(session, workspace)
    try:
        visit = count_visit(
            session, workspace=workspace, customer=customer, stand_settings=stand_settings
        )
    except PlateTooSoon as exc:
        last = visit_action.last_for_customer(session, customer_id=customer.id)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This plate is already counted",
                "seconds_left": exc.seconds_left,
                "customer": customer_view(customer, last, stand_settings, session),
            },
        )

    jara = jara_action.get_by_all(session, visit_id=visit.id)
    # A crew jara can go to another member: then `jara` is None here and crew.jara_to names
    # the winner, who sees the code on their own page (customer.open_jara).
    mine = jara is not None and jara.customer_id == customer.id
    return {
        "customer": customer_view(customer, visit, stand_settings, session),
        "returning": returning,
        "visit_id": visit.id,
        "plate_number": visit.plate_number,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "jara": {"code": jara.code} if mine else None,
        "crew": lunch_crew.count_result(
            session, visit=visit, customer_id=customer.id, stand_settings=stand_settings
        ),
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
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Forget this customer at this stand: chats, ratings, jara, plates, then the customer."""
    # Plate Ajo refuses (409) while prepaid plates remain, before anything is deleted.
    for feature in (plate_ajo, pot_alert, lunch_crew):
        feature.forget_customer(session, workspace=workspace, customer=customer)
    forget_customer(session, workspace=workspace, customer=customer)
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
    if customer is not None:
        record_turn(session, workspace=workspace, customer=customer, question=body.message, answer=reply)
    return {"reply": reply, "source": source}
