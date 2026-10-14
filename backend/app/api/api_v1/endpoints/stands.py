"""Vendor routes: create a stand, see the live dashboard, edit the character.

Sign-in comes from MSFLib auth (bearer token). Dashboard routes carry the
stand's slug, and MSFLib's workspace dependencies check the vendor is a member.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, func, select

from app.actions import character_action, jara_action, workspace_action
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
from app.services import alerts, prize_wheel, sms_alerts, stand_photo
from app.services.bisi import suggest_character
from app.services.chat_log import recent_questions
from app.services.qr import scan_code
from app.services.stand_photo import PhotoError
from app.services.stands import create_stand, last_plates, resolve_stand_settings, set_stand_setting

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
        "photo": stand_photo.photo_path(session, workspace),
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
    stand_settings = resolve_stand_settings(session, workspace)
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

    open_jara = session.exec(
        select(JaraReward, Customer)
        .join(Customer, Customer.id == JaraReward.customer_id)
        .where(JaraReward.workspace_id == ws, JaraReward.redeemed == False)
        .order_by(JaraReward.id.desc())
        .limit(10)
    ).all()

    wheel_live = prize_wheel.live_for(session, workspace.id, stand_settings)
    return {
        "stand": stand_view(session, workspace),
        "open_jara": [
            {
                "code": j.code,
                "name": c.first_name or "Guest",
                "at": j.created_at,
                # The Prize Wheel: what the spin won, or that the customer has not spun yet.
                "prize": (p.name if (p := prize_wheel.prize_for(session, j)) else None),
                "spin_pending": p is None and wheel_live,
            }
            for j, c in open_jara
        ],
        "recent_questions": recent_questions(session, workspace=workspace),
        "last_plates": last_plates(stand_settings),
        # Phones that get "last plates" alerts: push subscriptions plus text-message numbers.
        "alert_subscribers": alerts.subscriber_count(session, workspace=workspace)
        + sms_alerts.subscriber_count(session, workspace=workspace),
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
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


@router.post("/{workspace_slug}/jara/{code}/redeem")
def redeem_jara(
    code: str,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """The vendor gives the free portion (or the prize the wheel picked) and marks the code
    used, so it works only once."""
    jara = jara_action.get_by_all(session, workspace_id=workspace.id, code=prize_wheel.normalize_code(code))
    if jara is None:
        raise HTTPException(status_code=404, detail="No jara with that code at this stand")
    if jara.redeemed:
        raise HTTPException(status_code=409, detail="This jara was already used")
    try:
        prize_wheel.on_redeem(session, jara, datetime.now(UTC).replace(tzinfo=None))
    except prize_wheel.WheelError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    # Only one of two taps at once can mark it: the row changes only while it is still unused.
    marked = session.execute(
        update(JaraReward).where(JaraReward.id == jara.id, JaraReward.redeemed == False).values(redeemed=True)
    )
    if marked.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail="This jara was already used")
    session.commit()
    prize = prize_wheel.prize_for(session, jara)
    return {"code": jara.code, "redeemed": True, "prize": prize.name if prize else None}


class LastPlatesRequest(BaseModel):
    plates_left: int = Field(ge=0, le=500)
    minutes: int = Field(default=90, ge=5, le=360)


@router.post("/{workspace_slug}/last-plates")
def announce_last_plates(
    body: LastPlatesRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Tell customers how many plates are left tonight, stored as a per-stand tiered setting.
    plates_left=0 ends the announcement."""
    now = datetime.utcnow()
    until = (now + timedelta(minutes=body.minutes)).isoformat(timespec="seconds")
    set_stand_setting(session, workspace, "LAST_PLATES_LEFT", body.plates_left)
    set_stand_setting(session, workspace, "LAST_PLATES_UNTIL", until if body.plates_left else None)
    session.commit()
    stand_settings = resolve_stand_settings(session, workspace)
    alert = {"sent": 0, "texts": 0, "skipped": "ended"}
    if body.plates_left:
        # Push and text the news to customers' phones, in the character's voice (services/alerts.py).
        alert = alerts.send_last_plates(
            session,
            workspace=workspace,
            character=character_action.get_for_stand(session, workspace_id=workspace.id),
            stand_settings=stand_settings,
            plates_left=body.plates_left,
            until=until,
            now=now,
        )
    return {"last_plates": last_plates(stand_settings), "alert": alert}


@router.get("/{workspace_slug}/qr")
def read_qr(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """The scan code to put in the stand's QR code. Only stand members can read it."""
    stand_settings = resolve_stand_settings(session, workspace)
    return {"scan": scan_code(workspace, stand_settings), "version": stand_settings.QR_VERSION}


@router.post("/{workspace_slug}/qr/new")
def make_new_qr(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """A new QR code, for when the old one was copied or photographed. Older prints stop
    counting plates; the vendor prints or shows the new one."""
    version = resolve_stand_settings(session, workspace).QR_VERSION + 1
    set_stand_setting(session, workspace, "QR_VERSION", version)
    session.commit()
    return read_qr(workspace=workspace, _member=_member, session=session)


class PhotoRequest(BaseModel):
    # A data URL (data:image/jpeg;base64,...). The phone shrinks the photo first.
    data_url: str = Field(min_length=30, max_length=1_300_000)


@router.put("/{workspace_slug}/photo")
def upload_photo(
    body: PhotoRequest,
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    """Set (or replace) the photo of the stand."""
    try:
        stand_photo.save(session, workspace, body.data_url)
    except PhotoError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return stand_view(session, workspace)


@router.delete("/{workspace_slug}/photo")
def remove_photo(
    workspace: Workspace = Depends(deps.get_current_workspace),
    _member=Depends(deps.get_current_active_member),
    session: Session = Depends(deps.get_session),
) -> dict[str, Any]:
    stand_photo.remove(session, workspace)
    return stand_view(session, workspace)
