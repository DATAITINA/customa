"""Customer routes: what a phone sees after scanning a stand's QR code.

No login. The stand is found from the slug in the URL (MSFLib workspace
lookup), and the customer is recognised by a random key their phone keeps and
sends back in the X-Customer-Key header.
"""

import base64
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, Response
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
from app.services import (
    alerts,
    card_recovery,
    character_chat,
    lunch_crew,
    payments,
    plate_ajo,
    prize_wheel,
    regulars,
    sms_alerts,
    stand_photo,
    visit_plans,
)
from app.services.bisi import ChatContext, chat_reply
from app.services.chat_log import forget_customer, record_turn
from app.services.plates import count_visit
from app.services.qr import is_genuine_scan
from app.services.stands import last_plates, resolve_stand_settings

router = APIRouter(prefix="/public/{workspace_slug}", tags=["customer"])


class CountPlateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=40)
    consent: bool = False
    # "qr" when the page was opened from the stand's QR code. Saved once, when the
    # customer is first created, so the vendor can see how customers arrive.
    source: str | None = Field(default=None, max_length=20)
    # The scan code from the stand's QR code. A plate counts only with it (services/qr.py).
    scan: str | None = Field(default=None, max_length=40)


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


SCAN_REQUIRED = {
    "code": "scan_required",
    "message": "Scan the QR code at the stand to count your plate.",
}


def require_genuine_scan(code: str | None, workspace: Workspace, stand_settings: CustomaSettings) -> None:
    """403 unless `code` is the scan code from this stand's current QR code."""
    if not is_genuine_scan(code, workspace, stand_settings):
        raise HTTPException(status_code=403, detail=SCAN_REQUIRED)


def head_start(stand_settings: CustomaSettings) -> int:
    """The head-start card's gift stamps: 0 (off) up to 10."""
    return max(0, min(10, stand_settings.HEAD_START_STAMPS))


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
    open_jara: list[dict[str, Any]] = []
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
        # With the Prize Wheel live, an unspun jara shows as a spin (its code comes with the prize).
        wheel_live = prize_wheel.live_for(session, customer.workspace_id, stand_settings)
        open_jara = [
            prize_wheel.open_jara_entry(session, j, wheel_live)
            for j in jara_action.open_for_customer(
                session, workspace_id=customer.workspace_id, customer_id=customer.id
            )
        ]
    return {
        # The key this browser uses (its own key after card recovery), never another browser's.
        "key": getattr(customer, "_presented_key", None) or customer.key,
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
        # Gift stamps shown first on every new own card (display only, see HEAD_START_STAMPS).
        "head_start": head_start(stand_settings),
        "window_seconds": stand_settings.PLATE_WINDOW_SECONDS,
        "last_plates": last_plates(stand_settings),
        "customer": customer_view(customer, last, stand_settings, session) if customer else None,
        "photo": stand_photo.photo_path(session, workspace),
        # Which optional cards to show, so the page does not ask each feature separately.
        "features": {
            "plate_ajo": stand_settings.PLATE_AJO_ENABLED,
            "lunch_crew": stand_settings.LUNCH_CREW_ENABLED,
            "alerts": alerts.alerts_available() or sms_alerts.sms_available(),
            "prize_wheel": prize_wheel.live_for(session, workspace.id, stand_settings),
        },
    }


@router.get("/photo")
def read_photo(
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> Response:
    """The stand's photo. Its URL carries the version (?v=), so phones may keep it for good."""
    row = stand_photo.get(session, workspace)
    if row is None:
        raise HTTPException(status_code=404, detail="This stand has no photo yet")
    return Response(
        content=base64.b64decode(row.data),
        media_type=row.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


_KEY_SHAPE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


@router.get("/manifest")
def install_manifest(
    k: str | None = None,
    workspace: Workspace = Depends(deps.get_stand_public),
    session: Session = Depends(deps.get_session),
) -> JSONResponse:
    """The web app manifest for "Add to Home Screen" on this stand's page.

    The installed app opens on this stand, not the homepage. On iPhone, a Home Screen app has
    its own storage, separate from Safari, so it would not know the customer: their key (`k`,
    from their own phone) goes into the start URL, and the page stores it on first launch.
    Served through the web app's own domain (frontend vercel.json rewrite /m/{slug}).
    """
    start = f"/s/{workspace.slug}?app=1"
    if k and _KEY_SHAPE.match(k) and customer_action.get_by_key(session, workspace_id=workspace.id, key=k):
        start += f"&k={k}"
    name = workspace.name
    manifest = {
        "id": f"/s/{workspace.slug}",
        "name": f"{name} · Customa",
        "short_name": name if len(name) <= 14 else "Customa",
        "description": "Your food spot's loyalty card. Scan, eat, come back, get jara.",
        "start_url": start,
        "scope": "/",
        "display": "standalone",
        "background_color": "#FFFFFF",
        "theme_color": "#FDE6E2",
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JSONResponse(manifest, media_type="application/manifest+json", headers={"Cache-Control": "no-store"})


@router.post("/visits")
def count_plate(
    body: CountPlateRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    stand_settings = resolve_stand_settings(session, workspace)
    # Only a real scan counts: not a bookmark, the browser history or a shared link.
    require_genuine_scan(body.scan, workspace, stand_settings)
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
                source="qr",
            ),
        )

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
        "jara": _jara_result(session, jara, stand_settings) if mine else None,
        # A jara on a plate that is not the jara plate: the vendor's surprise (own card only).
        "surprise": mine and visit.plate_number != stand_settings.PLATES_FOR_JARA,
        "crew": lunch_crew.count_result(
            session, visit=visit, customer_id=customer.id, stand_settings=stand_settings
        ),
        # Plan the next visit: "kept" (this plate was in the planned slot) or "missed" (said once).
        "plan_outcome": visit_plans.outcome_for_visit(session, visit),
    }


def _jara_result(session: Session, jara: JaraReward, stand_settings: CustomaSettings) -> dict[str, Any]:
    """The jara just earned: its code, or, with the Prize Wheel live, a spin (the code comes with
    the prize the wheel picks)."""
    if prize_wheel.live_for(session, jara.workspace_id, stand_settings):
        return {"code": None, "spin": jara.id}
    return {"code": jara.code}


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
    for feature in (plate_ajo, lunch_crew, prize_wheel, regulars, visit_plans, payments, card_recovery):
        feature.forget_customer(session, workspace=workspace, customer=customer)
    forget_customer(session, workspace=workspace, customer=customer)
    character_chat.delete_memory(session, customer=customer)
    alerts.forget_customer(session, workspace=workspace, customer=customer)
    sms_alerts.forget_customer(session, workspace=workspace, customer=customer)
    for model, action in ((Rating, rating_action), (JaraReward, jara_action), (Visit, visit_action)):
        action.delete_multi_by_expressions(session, model.customer_id == customer.id)
    customer_action.delete(session, customer.id)
    return {"deleted": True}


def _chat_parts(session: Session, workspace: Workspace, customer: Customer | None):
    """The character, the customer's chat memory (this visit's chat opened if a new plate was
    counted) and their last plate. Chat is for customers with a counted plate."""
    character = character_action.get_for_stand(session, workspace_id=workspace.id)
    if character is None:
        raise HTTPException(status_code=404, detail="This stand has no character yet")
    if customer is None or visit_action.last_for_customer(session, customer_id=customer.id) is None:
        raise HTTPException(status_code=403, detail="Count a plate first, then we can talk!")
    stand_settings = resolve_stand_settings(session, workspace)
    memory = character_chat.memory_for(session, customer=customer)
    last = character_chat.start_or_resume(
        session, memory=memory, character=character, customer=customer, stand_settings=stand_settings
    )
    return character, memory, last, stand_settings


def _chat_view(memory, last: Visit | None, stand_settings: CustomaSettings) -> dict[str, Any]:
    return {
        **character_chat.chat_status(memory, last, stand_settings),
        "seconds_left": seconds_left(last, stand_settings),
        "memory": character_chat.memory_view(memory),
        "special": character_chat.todays_special(stand_settings),
    }


@router.get("/chat")
def read_chat(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """This visit's chat: open or not, the character's opening line, and what it remembers."""
    _, memory, last, stand_settings = _chat_parts(session, workspace, customer)
    session.commit()
    return _chat_view(memory, last, stand_settings)


@router.post("/chat")
def chat(
    body: ChatRequest,
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer | None = Depends(get_customer_or_none),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Talk to the stand's character (MSFLib ai-core, with a no-AI fallback).

    One short chat per counted plate: the last allowed message gets a warm cliffhanger reply
    and the chat opens again on the next plate. Private: only food questions are saved for the
    vendor (services/chat_log); the rest is never shown to them.
    """
    character, memory, last, stand_settings = _chat_parts(session, workspace, customer)
    status = character_chat.chat_status(memory, last, stand_settings)
    if not status["open"]:
        session.commit()
        return {"reply": None, "source": None, "chat": _chat_view(memory, last, stand_settings)}

    memory.messages_used += 1
    closing = memory.messages_used >= stand_settings.CHAT_MESSAGES_PER_PLATE
    character_chat.remember_from_message(memory, body.message, character)
    ctx = ChatContext(
        stand_name=workspace.name,
        customer_name=customer.first_name,
        plate=last.plate_number if last else 0,
        total=stand_settings.PLATES_FOR_JARA,
        special=character_chat.todays_special(stand_settings),
        favourite_item=memory.favourite_item,
        last_item=memory.last_item,
        closing=closing,
        seed=customer.id,
    )
    if character_chat.wants_joke(body.message) and not closing:
        reply, source, follow_up = character_chat.joke_of_the_day(memory.messages_used), "quick", None
    else:
        reply, source, follow_up = chat_reply(
            character=character, ctx=ctx, message=body.message, history=body.history,
            workspace_id=workspace.id,
        )
    if closing:
        memory.closed = True
        memory.follow_up = follow_up
    session.add(memory)
    session.commit()
    if character_chat.is_food_question(body.message, character):
        record_turn(session, workspace=workspace, customer=customer, question=body.message, answer=reply)
    return {"reply": reply, "source": source, "chat": _chat_view(memory, last, stand_settings)}


@router.delete("/chat/memory")
def forget_chat_memory(
    workspace: Workspace = Depends(deps.get_stand_public),
    customer: Customer = Depends(require_customer),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """The customer clears what the character remembers about them."""
    memory = character_chat.memory_for(session, customer=customer)
    character_chat.forget_memory(memory)
    session.add(memory)
    session.commit()
    return {"memory": character_chat.memory_view(memory)}
