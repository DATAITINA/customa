"""Plate Ajo: prepaid plates at today's price.

A customer prepays the vendor for 5 or 10 plates of one menu item. Money never passes through
Customa: the customer transfers to the vendor's own bank account, taps "I have sent it", and the
vendor confirms the transfer on the dashboard. Customa keeps the plate count only.

Every function takes explicit arguments and uses plain session.exec / add / commit, so it can be
tested without MSFLib. The endpoints in api/api_v1/endpoints/plate_ajo.py stay thin.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from ..actions import PlateTooSoon
from ..core.config import CustomaSettings
from ..models import Customer, JaraReward, PlateBundle, PlateUse, Workspace
from . import plates

logger = logging.getLogger("customa.plate_ajo")

BUNDLE_SIZES = (5, 10)
USE_GUARD_SECONDS = 60  # double tap protection between two prepaid plates
NIGERIA_UTC_OFFSET = timedelta(hours=1)  # West Africa Time, no daylight saving
NAME_MAX = 60

PENDING, ACTIVE, REJECTED, FINISHED = "pending", "active", "rejected", "finished"

NOT_KNOWN = "We don't know you at this stand yet"
NOT_AVAILABLE = "Plate Ajo is not open at this stand right now"
STILL_HAS_PLATES = (
    "You still have prepaid plates at this stand. Use them or ask the vendor before deleting "
    "your data."
)


def utcnow() -> datetime:
    """Naive UTC, like every timestamp the app stores and compares."""
    return datetime.now(UTC).replace(tzinfo=None)


def nigeria_day_start(now: datetime | None = None) -> datetime:
    """00:00 today in Nigeria (UTC+1), as naive UTC."""
    local = (now or utcnow()) + NIGERIA_UTC_OFFSET
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - NIGERIA_UTC_OFFSET


# --- Settings and menu -----------------------------------------------------------------------


def bank_details(stand_settings: CustomaSettings) -> dict[str, str] | None:
    """The vendor's account, or None unless all three details are set."""
    bank = (stand_settings.AJO_BANK_NAME or "").strip()
    number = (stand_settings.AJO_ACCOUNT_NUMBER or "").strip()
    name = (stand_settings.AJO_ACCOUNT_NAME or "").strip()
    if not bank or not re.fullmatch(r"\d{10}", number) or not name:
        return None
    return {"bank_name": bank, "account_number": number, "account_name": name}


def is_available(stand_settings: CustomaSettings) -> bool:
    """Customers can start a new bundle only when the vendor turned Ajo on with full details."""
    return bool(stand_settings.PLATE_AJO_ENABLED) and bank_details(stand_settings) is not None


def menu_items(menu: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Menu items that have a name and a positive whole-naira price."""
    items = []
    for entry in menu or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("item") or "").strip()
        price = entry.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, float, str)):
            continue
        try:
            price = int(float(price))
        except ValueError:
            continue
        if name and price > 0:
            items.append({"item": name, "price": price})
    return items


def validate_settings(
    stand_settings: CustomaSettings,
    *,
    enabled: bool,
    bank_name: str | None = None,
    account_number: str | None = None,
    account_name: str | None = None,
) -> dict[str, Any]:
    """Check the vendor's form and return the setting values to store.

    A field left out (None) keeps its saved value; an empty string clears it.
    """

    def pick(new: str | None, saved: str | None) -> str | None:
        value = (saved if new is None else new) or ""
        value = " ".join(value.split())
        return value or None

    bank = pick(bank_name, stand_settings.AJO_BANK_NAME)
    name = pick(account_name, stand_settings.AJO_ACCOUNT_NAME)
    number = pick(account_number, stand_settings.AJO_ACCOUNT_NUMBER)
    if number is not None:
        number = number.replace(" ", "").replace("-", "")
        if not re.fullmatch(r"\d{10}", number):
            raise HTTPException(400, detail="The account number must be exactly 10 digits.")
    for label, value in (("Bank name", bank), ("Account name", name)):
        if value is not None and len(value) > NAME_MAX:
            raise HTTPException(400, detail=f"{label} must be {NAME_MAX} characters or fewer.")
    if enabled and not (bank and number and name):
        raise HTTPException(
            400,
            detail="To turn on Plate Ajo, enter your bank name, 10-digit account number "
            "and account name.",
        )
    return {
        "PLATE_AJO_ENABLED": bool(enabled),
        "AJO_BANK_NAME": bank,
        "AJO_ACCOUNT_NUMBER": number,
        "AJO_ACCOUNT_NAME": name,
    }


# --- Views -----------------------------------------------------------------------------------


def bundle_view(bundle: PlateBundle) -> dict[str, Any]:
    return {
        "id": bundle.id,
        "item": bundle.item,
        "unit_price": bundle.unit_price,
        "plates_total": bundle.plates_total,
        "plates_used": bundle.plates_used,
        "plates_left": max(0, bundle.plates_total - bundle.plates_used),
        "status": bundle.status,
        "created_at": bundle.created_at,
    }


def customer_state(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer | None,
    stand_settings: CustomaSettings,
    menu: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """What the customer's Ajo card shows. Works without a customer (no bundles yet)."""
    available = is_available(stand_settings)
    bundles: list[PlateBundle] = []
    if customer is not None:
        bundles = list(
            session.exec(
                select(PlateBundle)
                .where(
                    PlateBundle.workspace_id == workspace.id,
                    PlateBundle.customer_id == customer.id,
                )
                .order_by(PlateBundle.id.desc())
                .limit(20)
            ).all()
        )
    return {
        "available": available,
        "bank": bank_details(stand_settings) if available else None,
        "items": menu_items(menu) if available else [],
        "bundle_sizes": list(BUNDLE_SIZES),
        "bundles": [bundle_view(b) for b in bundles],
    }


# --- Customer actions ------------------------------------------------------------------------


def _lock_customer(session: Session, customer: Customer) -> None:
    """Serialise this customer's Ajo writes (double tap, retries, two tabs).
    Postgres honours FOR UPDATE; SQLite ignores it."""
    session.exec(select(Customer).where(Customer.id == customer.id).with_for_update()).one()


def create_bundle(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    stand_settings: CustomaSettings,
    menu: list[dict[str, Any]] | None,
    item: str,
    plates: int,
    payer_name: str,
) -> PlateBundle:
    """The customer says they sent the transfer: a pending bundle at today's menu price."""
    if not is_available(stand_settings):
        raise HTTPException(403, detail=NOT_AVAILABLE)
    if plates not in BUNDLE_SIZES:
        raise HTTPException(400, detail="Choose 5 or 10 plates.")
    wanted = " ".join((item or "").split()).casefold()
    on_menu = next((m for m in menu_items(menu) if m["item"].casefold() == wanted), None)
    if on_menu is None:
        raise HTTPException(400, detail="That item is not on this stand's menu.")
    payer = " ".join((payer_name or "").split())
    if not 2 <= len(payer) <= NAME_MAX:
        raise HTTPException(
            400, detail=f"Enter the name on your transfer (2 to {NAME_MAX} characters)."
        )

    _lock_customer(session, customer)
    pending = session.exec(
        select(PlateBundle).where(
            PlateBundle.workspace_id == workspace.id,
            PlateBundle.customer_id == customer.id,
            PlateBundle.status == PENDING,
        )
    ).first()
    if pending is not None:
        session.rollback()
        raise HTTPException(
            409, detail="You already have a transfer waiting for the vendor to confirm."
        )

    now = utcnow()
    bundle = PlateBundle(
        workspace_id=workspace.id,
        customer_id=customer.id,
        item=on_menu["item"],
        unit_price=on_menu["price"],  # read from the menu here, never from the client
        plates_total=plates,
        plates_used=0,
        status=PENDING,
        payer_name=payer,
        created_at=now,
        updated_at=now,
    )
    session.add(bundle)
    session.commit()
    session.refresh(bundle)
    return bundle


def use_plate(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    stand_settings: CustomaSettings,
) -> dict[str, Any]:
    """Use one prepaid plate from the oldest active bundle, then try to count a stamp.

    Works even if the vendor has since turned Ajo off: those plates are already paid for.
    """
    _lock_customer(session, customer)
    bundle = session.exec(
        select(PlateBundle)
        .where(
            PlateBundle.workspace_id == workspace.id,
            PlateBundle.customer_id == customer.id,
            PlateBundle.status == ACTIVE,
            PlateBundle.plates_used < PlateBundle.plates_total,
        )
        .order_by(PlateBundle.id)
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if bundle is None:
        session.rollback()
        raise HTTPException(409, detail="You have no prepaid plates left at this stand.")

    now = utcnow()
    last_use = session.exec(
        select(PlateUse)
        .where(PlateUse.workspace_id == workspace.id, PlateUse.customer_id == customer.id)
        .order_by(PlateUse.id.desc())
        .limit(1)
    ).first()
    if last_use is not None and now - last_use.created_at < timedelta(seconds=USE_GUARD_SECONDS):
        session.rollback()
        raise HTTPException(
            409, detail="A prepaid plate was just used. Wait a minute before using another one."
        )

    bundle.plates_used += 1
    if bundle.plates_used >= bundle.plates_total:
        bundle.status = FINISHED
    bundle.updated_at = now
    use = PlateUse(
        workspace_id=workspace.id,
        bundle_id=bundle.id,
        customer_id=customer.id,
        plate_number=bundle.plates_used,
        created_at=now,
        updated_at=now,
    )
    session.add(bundle)
    session.add(use)
    session.commit()
    session.refresh(bundle)
    session.refresh(use)

    result: dict[str, Any] = {
        "bundle": bundle_view(bundle),
        "use": {
            "item": bundle.item,
            "plate_number": use.plate_number,
            "plates_total": bundle.plates_total,
            "at": use.created_at,
        },
        "stamp": {"counted": False, "plate_number": None, "jara": None},
    }

    # The prepaid plate is saved. Counting a stamp follows the normal 6-hour rule and must
    # never undo or hide the plate just used, so any failure here only means "not counted".
    try:
        visit = plates.count_visit(
            session, workspace=workspace, customer=customer, stand_settings=stand_settings
        )
    except PlateTooSoon:
        session.rollback()
        return result
    except Exception:
        session.rollback()
        logger.exception("prepaid plate used but the stamp could not be counted")
        return result

    jara = session.exec(select(JaraReward).where(JaraReward.visit_id == visit.id)).first()
    # A Lunch Crew jara can go to another member; only show this customer's own code.
    own_jara = jara is not None and jara.customer_id == customer.id
    result["stamp"] = {
        "counted": True,
        "plate_number": visit.plate_number,
        "jara": {"code": jara.code} if own_jara else None,
    }
    return result


# --- Vendor actions --------------------------------------------------------------------------


def vendor_state(
    session: Session, *, workspace: Workspace, stand_settings: CustomaSettings
) -> dict[str, Any]:
    """The dashboard panel: settings, transfers to confirm, plates left, plates served today."""

    def name_of(c: Customer) -> str:
        return c.first_name or "Guest"

    pending = session.exec(
        select(PlateBundle, Customer)
        .join(Customer, Customer.id == PlateBundle.customer_id)
        .where(PlateBundle.workspace_id == workspace.id, PlateBundle.status == PENDING)
        .order_by(PlateBundle.id)
    ).all()
    active = session.exec(
        select(PlateBundle, Customer)
        .join(Customer, Customer.id == PlateBundle.customer_id)
        .where(PlateBundle.workspace_id == workspace.id, PlateBundle.status == ACTIVE)
        .order_by(PlateBundle.id)
    ).all()
    served = session.exec(
        select(PlateUse, PlateBundle, Customer)
        .join(PlateBundle, PlateBundle.id == PlateUse.bundle_id)
        .join(Customer, Customer.id == PlateUse.customer_id)
        .where(PlateUse.workspace_id == workspace.id, PlateUse.created_at >= nigeria_day_start())
        .order_by(PlateUse.id.desc())
        .limit(100)
    ).all()

    return {
        "enabled": bool(stand_settings.PLATE_AJO_ENABLED),
        "bank_name": stand_settings.AJO_BANK_NAME,
        "account_number": stand_settings.AJO_ACCOUNT_NUMBER,
        "account_name": stand_settings.AJO_ACCOUNT_NAME,
        "available": is_available(stand_settings),
        "pending": [
            {
                "id": b.id,
                "name": name_of(c),
                "payer_name": b.payer_name,
                "item": b.item,
                "plates_total": b.plates_total,
                "unit_price": b.unit_price,
                "total": b.unit_price * b.plates_total,
                "created_at": b.created_at,
            }
            for b, c in pending
        ],
        "active": [
            {
                "id": b.id,
                "name": name_of(c),
                "item": b.item,
                "unit_price": b.unit_price,
                "plates_total": b.plates_total,
                "plates_used": b.plates_used,
                "plates_left": max(0, b.plates_total - b.plates_used),
                "confirmed_at": b.confirmed_at,
            }
            for b, c in active
        ],
        "served_today": [
            {
                "id": u.id,
                "name": name_of(c),
                "item": b.item,
                "plate_number": u.plate_number,
                "plates_total": b.plates_total,
                "at": u.created_at,
            }
            for u, b, c in served
        ],
    }


def decide_bundle(
    session: Session, *, workspace: Workspace, bundle_id: int, confirm: bool
) -> PlateBundle:
    """The vendor confirms (pending -> active) or rejects (pending -> rejected) a transfer."""
    bundle = session.exec(
        select(PlateBundle)
        .where(PlateBundle.id == bundle_id, PlateBundle.workspace_id == workspace.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if bundle is None:
        session.rollback()
        raise HTTPException(404, detail="No such prepaid bundle at this stand")
    if bundle.status != PENDING:
        session.rollback()
        raise HTTPException(409, detail=f"This bundle is already {bundle.status}")
    now = utcnow()
    bundle.status = ACTIVE if confirm else REJECTED
    if confirm:
        bundle.confirmed_at = now
    bundle.updated_at = now
    session.add(bundle)
    session.commit()
    session.refresh(bundle)
    return bundle


# --- Delete my data --------------------------------------------------------------------------


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's plate_ajo data at this stand (called by "Delete my data").

    Refuses while the customer still has paid-for plates or a transfer waiting, so nobody
    loses money by accident. Called before anything else is deleted. Does not commit: the
    deletes are flushed now, in this order, and the caller's commit makes them permanent.
    """
    bundles = list(
        session.exec(
            select(PlateBundle).where(
                PlateBundle.workspace_id == workspace.id,
                PlateBundle.customer_id == customer.id,
            )
        ).all()
    )
    for b in bundles:
        if b.status == PENDING or (b.status == ACTIVE and b.plates_used < b.plates_total):
            raise HTTPException(409, detail=STILL_HAS_PLATES)
    if not bundles:
        return
    uses = session.exec(
        select(PlateUse).where(
            PlateUse.workspace_id == workspace.id, PlateUse.customer_id == customer.id
        )
    ).all()
    for u in uses:
        session.delete(u)
    session.flush()
    for b in bundles:
        session.delete(b)
    session.flush()
