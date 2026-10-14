"""Prize Wheel: a jara becomes one spin on the vendor's wheel of food prizes.

- The vendor adds up to MAX_ITEMS food prizes (name, prize, photo, how often it comes up) and
  publishes the wheel (at least MIN_TO_PUBLISH available prizes).
- Each jara (plate 6, a surprise jara, a crew turn) is one spin. The server picks the prize
  (secure random, weighted by each slice's size) and where the pointer stops; the phone only
  animates that result. Spinning again with the same jara returns the same result.
- At the spin the jara gets a new, longer redemption code, shown with the prize. The vendor
  checks it (valid, used, expired, another stand's) and marks it given: once only.
"""

import base64
import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from ..core.config import CustomaSettings
from ..models import Customer, JaraPrize, JaraReward, WheelItem, Workspace
from . import stand_photo
from .stands import resolve_stand_settings, set_stand_setting

MAX_ITEMS = 6
MIN_TO_PUBLISH = 2
WEIGHTS = (1, 3, 5)  # rarely, sometimes, often
PHOTO_MAX_BYTES = 600 * 1024
# Redemption codes: no 0/O or 1/I, so they are easy to read out and type.
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_rng = secrets.SystemRandom()


class WheelError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# --- The vendor's wheel ---------------------------------------------------------------------


def items(session: Session, workspace: Workspace) -> list[WheelItem]:
    return list(
        session.exec(
            select(WheelItem).where(WheelItem.workspace_id == workspace.id).order_by(WheelItem.position, WheelItem.id)
        ).all()
    )


def on_wheel(session: Session, workspace: Workspace) -> list[WheelItem]:
    """The prizes a spin can land on: the available ones."""
    return [i for i in items(session, workspace) if i.available]


def photo_path(workspace: Workspace, item: WheelItem) -> str | None:
    return f"/public/{workspace.slug}/wheel/items/{item.id}/photo?v={item.photo_version}" if item.photo_data else None


def item_view(workspace: Workspace, item: WheelItem, *, vendor: bool = False) -> dict[str, Any]:
    view = {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "prize": item.prize,
        "weight": item.weight,
        "photo": photo_path(workspace, item),
    }
    if vendor:
        view["available"] = item.available
    return view


def _clean(text: str | None, limit: int) -> str | None:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] or None


def _set_fields(item: WheelItem, data: dict[str, Any]) -> None:
    if "name" in data:
        name = _clean(data["name"], 40)
        if not name:
            raise WheelError(400, "Give the food a name.")
        item.name = name
    if "description" in data:
        item.description = _clean(data["description"], 120)
    if "prize" in data:
        item.prize = _clean(data["prize"], 60)
    if "weight" in data and data["weight"] is not None:
        if data["weight"] not in WEIGHTS:
            raise WheelError(400, "Choose how often: often, sometimes or rarely.")
        item.weight = data["weight"]
    if "available" in data and data["available"] is not None:
        item.available = bool(data["available"])


def _set_photo(item: WheelItem, data_url: str | None) -> None:
    if data_url is None:
        if item.photo_data:
            item.photo_type, item.photo_data = None, None
            item.photo_version += 1
        return
    try:
        content_type, raw = stand_photo.decode(data_url)
    except stand_photo.PhotoError as exc:
        raise WheelError(400, exc.message)
    if len(raw) > PHOTO_MAX_BYTES:
        raise WheelError(400, "That photo is too big. Try again, the app shrinks it for you.")
    item.photo_type, item.photo_data = content_type, base64.b64encode(raw).decode()
    item.photo_version += 1


def add_item(session: Session, workspace: Workspace, data: dict[str, Any]) -> WheelItem:
    current = items(session, workspace)
    if len(current) >= MAX_ITEMS:
        raise WheelError(409, f"Your wheel already has {MAX_ITEMS} prizes. Remove one to add another.")
    item = WheelItem(workspace_id=workspace.id, name="", position=(max((i.position for i in current), default=-1) + 1))
    _set_fields(item, {"name": data.get("name"), **{k: v for k, v in data.items() if k != "name"}})
    if data.get("photo"):
        _set_photo(item, data["photo"])
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_item(session: Session, workspace: Workspace, item_id: int) -> WheelItem:
    item = session.get(WheelItem, item_id)
    if item is None or item.workspace_id != workspace.id:
        raise WheelError(404, "That prize is not on your wheel.")
    return item


def update_item(session: Session, workspace: Workspace, item_id: int, data: dict[str, Any]) -> WheelItem:
    item = get_item(session, workspace, item_id)
    _set_fields(item, data)
    if "photo" in data:
        _set_photo(item, data["photo"])
    session.add(item)
    session.commit()
    session.refresh(item)
    _unpublish_if_too_few(session, workspace)
    return item


def delete_item(session: Session, workspace: Workspace, item_id: int) -> None:
    item = get_item(session, workspace, item_id)
    session.delete(item)  # prizes already won keep their copied name (item_id becomes NULL)
    session.commit()
    _unpublish_if_too_few(session, workspace)


def _unpublish_if_too_few(session: Session, workspace: Workspace) -> None:
    """A live wheel needs at least MIN_TO_PUBLISH available prizes; below that it pauses."""
    if resolve_stand_settings(session, workspace).PRIZE_WHEEL_ENABLED and len(on_wheel(session, workspace)) < MIN_TO_PUBLISH:
        set_stand_setting(session, workspace, "PRIZE_WHEEL_ENABLED", False)
        session.commit()


def publish(session: Session, workspace: Workspace, enabled: bool) -> None:
    if enabled and len(on_wheel(session, workspace)) < MIN_TO_PUBLISH:
        raise WheelError(409, f"Add at least {MIN_TO_PUBLISH} available prizes before you publish your wheel.")
    set_stand_setting(session, workspace, "PRIZE_WHEEL_ENABLED", enabled)
    session.commit()


def is_live(session: Session, workspace: Workspace, stand_settings: CustomaSettings) -> bool:
    return live_for(session, workspace.id, stand_settings)


def live_for(session: Session, workspace_id: int, stand_settings: CustomaSettings) -> bool:
    """The wheel is published and has enough available prizes to spin."""
    if not stand_settings.PRIZE_WHEEL_ENABLED:
        return False
    count = session.exec(
        select(func.count(WheelItem.id)).where(WheelItem.workspace_id == workspace_id, WheelItem.available == True)
    ).one()
    return count >= MIN_TO_PUBLISH


def vendor_view(session: Session, workspace: Workspace, stand_settings: CustomaSettings) -> dict[str, Any]:
    spins = session.exec(select(func.count(JaraPrize.id)).where(JaraPrize.workspace_id == workspace.id)).one()
    given = session.exec(
        select(func.count(JaraPrize.id)).where(JaraPrize.workspace_id == workspace.id, JaraPrize.redeemed_at.is_not(None))
    ).one()
    return {
        "enabled": is_live(session, workspace, stand_settings),
        "items": [item_view(workspace, i, vendor=True) for i in items(session, workspace)],
        "max_items": MAX_ITEMS,
        "min_to_publish": MIN_TO_PUBLISH,
        "valid_days": stand_settings.WHEEL_PRIZE_VALID_DAYS,
        "stats": {"spins": spins, "given": given},
    }


# --- Spins ----------------------------------------------------------------------------------


def prize_for(session: Session, jara: JaraReward) -> JaraPrize | None:
    return session.exec(select(JaraPrize).where(JaraPrize.jara_id == jara.id)).first()


def new_code(session: Session, workspace: Workspace) -> str:
    """JARA-XXXX-XXXX: about 10^12 possible codes, unique at this stand."""
    while True:
        raw = "".join(_rng.choice(CODE_ALPHABET) for _ in range(8))
        code = f"JARA-{raw[:4]}-{raw[4:]}"
        taken = session.exec(
            select(JaraReward.id).where(JaraReward.workspace_id == workspace.id, JaraReward.code == code)
        ).first()
        if taken is None:
            return code


def normalize_code(text: str) -> str:
    """What the vendor typed or scanned, as a stored code: JARA-XXXX-XXXX or JARA-XXXXXX."""
    letters = re.sub(r"[^A-Z0-9]", "", (text or "").upper())
    letters = letters.removeprefix("JARA")
    if len(letters) == 8:
        return f"JARA-{letters[:4]}-{letters[4:]}"
    return f"JARA-{letters}"


def prize_view(jara: JaraReward, prize: JaraPrize) -> dict[str, Any]:
    return {
        "code": jara.code,
        "name": prize.name,
        "prize": prize.prize,
        "photo": prize.photo_path,
        "expires_at": prize.expires_at,
        "redeemed": jara.redeemed,
    }


def spin_view(jara: JaraReward, prize: JaraPrize) -> dict[str, Any]:
    return {
        "jara_id": jara.id,
        "wheel": json.loads(prize.wheel),
        "slot": prize.slot,
        "landing": prize.landing,
        "prize": prize_view(jara, prize),
    }


def spin(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    jara_id: int,
    stand_settings: CustomaSettings,
    now: datetime,
) -> dict[str, Any]:
    """Spin the wheel with one of this customer's jara. The server decides; once per jara."""
    jara = session.get(JaraReward, jara_id)
    if jara is None or jara.workspace_id != workspace.id or jara.customer_id != customer.id:
        raise WheelError(404, "That spin is not yours.")
    done = prize_for(session, jara)
    if done is not None:
        return spin_view(jara, done)  # the same result, however often the phone asks
    if jara.redeemed:
        raise WheelError(409, "This jara was already given out.")
    if not stand_settings.PRIZE_WHEEL_ENABLED:
        raise WheelError(409, "The prize wheel is resting today. Show your jara code to the vendor.")
    slices = on_wheel(session, workspace)
    if len(slices) < MIN_TO_PUBLISH:
        raise WheelError(409, "The prize wheel is resting today. Show your jara code to the vendor.")

    slot = _rng.choices(range(len(slices)), weights=[i.weight for i in slices])[0]
    item = slices[slot]
    wheel = [{"id": i.id, "name": i.name, "weight": i.weight, "photo": photo_path(workspace, i)} for i in slices]
    jara.code = new_code(session, workspace)
    prize = JaraPrize(
        jara_id=jara.id,
        workspace_id=workspace.id,
        customer_id=customer.id,
        item_id=item.id,
        name=item.name,
        prize=item.prize,
        photo_path=photo_path(workspace, item),
        wheel=json.dumps(wheel),
        slot=slot,
        landing=round(_rng.uniform(0.2, 0.8), 3),
        expires_at=now + timedelta(days=stand_settings.WHEEL_PRIZE_VALID_DAYS),
    )
    session.add(jara)
    session.add(prize)
    try:
        session.commit()
    except IntegrityError:
        # Two taps at once: the other request's spin counts.
        session.rollback()
        jara = session.get(JaraReward, jara_id)
        prize = prize_for(session, jara)
        if prize is None:
            raise
    session.refresh(jara)
    session.refresh(prize)
    return spin_view(jara, prize)


def customer_state(
    session: Session, *, workspace: Workspace, customer: Customer | None, stand_settings: CustomaSettings
) -> dict[str, Any]:
    """The wheel for the customer page: the prizes, their spins waiting and prizes won."""
    live = is_live(session, workspace, stand_settings)
    spins: list[int] = []
    won: list[dict[str, Any]] = []
    if customer is not None:
        for jara in session.exec(
            select(JaraReward)
            .where(JaraReward.workspace_id == workspace.id, JaraReward.customer_id == customer.id, JaraReward.redeemed == False)
            .order_by(JaraReward.id)
        ).all():
            prize = prize_for(session, jara)
            if prize is not None:
                won.append({"jara_id": jara.id, **prize_view(jara, prize)})
            elif live:
                spins.append(jara.id)
    return {
        "enabled": live,
        "items": [item_view(workspace, i) for i in on_wheel(session, workspace)] if live else [],
        "spins": spins,
        "won": won,
    }


def open_jara_entry(session: Session, jara: JaraReward, wheel_live: bool) -> dict[str, Any]:
    """One of the customer's unredeemed jara on their card: its code, or its prize, or a spin."""
    prize = prize_for(session, jara)
    if prize is not None:
        return {"code": jara.code, "prize": prize.name, "expires_at": prize.expires_at}
    if wheel_live:
        return {"code": None, "spin": jara.id}  # the code comes with the spin
    return {"code": jara.code}


# --- The vendor checks and gives a prize ----------------------------------------------------


def check_code(session: Session, *, workspace: Workspace, code: str, now: datetime, wheel_live: bool) -> dict[str, Any]:
    """What a jara code is worth at this stand: valid, used, expired, not spun, another stand's."""
    code = normalize_code(code)
    jara = session.exec(select(JaraReward).where(JaraReward.workspace_id == workspace.id, JaraReward.code == code)).first()
    if jara is None:
        elsewhere = session.exec(select(JaraReward.id).where(JaraReward.code == code)).first()
        return {"status": "other_stand" if elsewhere else "unknown", "code": code}
    customer = session.get(Customer, jara.customer_id)
    prize = prize_for(session, jara)
    if jara.redeemed:
        status = "redeemed"
    elif prize is not None and prize.expires_at < now:
        status = "expired"
    elif prize is None and wheel_live:
        status = "not_spun"
    else:
        status = "valid"
    return {
        "status": status,
        "code": jara.code,
        "customer": (customer.first_name if customer else None) or "Guest",
        "issued_at": jara.created_at,
        "prize": (
            {
                "name": prize.name,
                "prize": prize.prize,
                "photo": prize.photo_path,
                "spun_at": prize.created_at,
                "expires_at": prize.expires_at,
                "redeemed_at": prize.redeemed_at,
            }
            if prize
            else None
        ),
    }


def on_redeem(session: Session, jara: JaraReward, now: datetime) -> None:
    """Before a jara is marked given: an expired prize cannot be; a valid one records when."""
    prize = prize_for(session, jara)
    if prize is None:
        return
    if prize.expires_at < now:
        raise WheelError(409, f"This prize expired on {prize.expires_at:%d %b}.")
    prize.redeemed_at = now
    session.add(prize)


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: the customer's spins (the caller commits)."""
    mine = select(JaraReward.id).where(JaraReward.customer_id == customer.id)
    for prize in session.exec(
        select(JaraPrize).where((JaraPrize.customer_id == customer.id) | (JaraPrize.jara_id.in_(mine)))
    ).all():
        session.delete(prize)
    session.flush()
