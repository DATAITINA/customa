"""Pot Alert: tell me when my dish is ready.

Customers pick menu dishes and leave a WhatsApp number. When a pot is ready the vendor taps
"Ready now": every customer sees a "ready now" banner for READY_WINDOW (or until the vendor ends
it), and the vendor gets the list of waiting customers to message from their own WhatsApp.
Customa never sends WhatsApp messages itself.

Every function takes explicit arguments and uses plain SQLModel queries, so it can be tested
without the web layer. Whether the feature is on is decided by the caller (stand settings).
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, delete, func, select

from ..models import Character, Customer, PotReady, PotWatch, Workspace

READY_WINDOW = timedelta(hours=3)
MAX_WATCH_ITEMS = 10
MAX_PLATES_LEFT = 500
PHONE_HELP = "Enter a Nigerian phone number, like 0803 123 4567 or +234 803 123 4567"


class PotAlertError(ValueError):
    """A request we refuse, with a message that can be shown to the person as is."""


def utcnow() -> datetime:
    # Naive UTC, like the timestamps the app stores and compares.
    return datetime.now(UTC).replace(tzinfo=None)


# --- Phone numbers -------------------------------------------------------------------------


def normalise_phone(raw: str | None) -> str:
    """A Nigerian mobile number as 234 + 10 digits (the form wa.me links need).

    Accepts 0803 123 4567, 08031234567, +2348031234567, 2348031234567, +234 0803... and
    8031234567, with spaces, dashes, dots or brackets. Anything else raises PotAlertError.
    """
    text = (raw or "").strip()
    compact = re.sub(r"[\s\-.()]", "", text)
    compact = compact.removeprefix("+")
    if not compact.isdigit():
        raise PotAlertError(PHONE_HELP)
    if len(compact) == 11 and compact.startswith("0"):
        national = compact[1:]
    elif len(compact) == 14 and compact.startswith("2340"):
        national = compact[4:]
    elif len(compact) == 13 and compact.startswith("234"):
        national = compact[3:]
    elif len(compact) == 10:
        national = compact
    else:
        raise PotAlertError(PHONE_HELP)
    # Nigerian mobile numbers start 070, 080, 081, 090, 091 (7, 8 or 9 after the 0).
    if national[0] not in "789":
        raise PotAlertError(PHONE_HELP)
    return "234" + national


def mask_phone(phone: str) -> str:
    """Only the last four digits, for showing a customer their own number back."""
    return "•••• " + phone[-4:]


# --- Menu ----------------------------------------------------------------------------------


def menu_items(session: Session, *, workspace: Workspace) -> list[str]:
    """The stand's menu dish names, in menu order, without blanks or repeats."""
    character = session.exec(
        select(Character).where(Character.workspace_id == workspace.id)
    ).first()
    names: list[str] = []
    seen: set[str] = set()
    for entry in (character.menu if character else None) or []:
        if not isinstance(entry, dict):
            continue
        name = " ".join(str(entry.get("item") or "").split())
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


def _menu_name(menu: list[str], item: str) -> str:
    """The menu's own spelling of `item` (case and spaces ignored), or PotAlertError."""
    wanted = " ".join(str(item or "").split()).casefold()
    for name in menu:
        if " ".join(name.split()).casefold() == wanted:
            return name
    raise PotAlertError(f'"{str(item or "").strip()}" is not on this stand\'s menu')


# --- Customer: watches ---------------------------------------------------------------------


def _watches(session: Session, *, workspace: Workspace, customer: Customer) -> list[PotWatch]:
    return list(
        session.exec(
            select(PotWatch)
            .where(PotWatch.workspace_id == workspace.id, PotWatch.customer_id == customer.id)
            .order_by(PotWatch.id)
        ).all()
    )


def set_watches(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    items: list[str],
    phone: str | None,
) -> list[PotWatch]:
    """Replace this customer's dish list (1 to MAX_WATCH_ITEMS menu dishes, one phone).

    An empty phone keeps the number the customer already gave (they only see it masked, so
    they cannot retype it to change dishes); a customer with no number yet must give one.
    """
    existing = {w.item: w for w in _watches(session, workspace=workspace, customer=customer)}
    if (phone or "").strip():
        normalised = normalise_phone(phone)
    elif existing:
        normalised = next(iter(existing.values())).phone
    else:
        raise PotAlertError("Enter your WhatsApp number")
    menu = menu_items(session, workspace=workspace)
    wanted: list[str] = []
    for item in items or []:
        name = _menu_name(menu, item)
        if name not in wanted:
            wanted.append(name)
    if not wanted:
        raise PotAlertError("Pick at least one dish")
    if len(wanted) > MAX_WATCH_ITEMS:
        raise PotAlertError(f"Pick at most {MAX_WATCH_ITEMS} dishes")

    # Change rows in place rather than delete-then-insert, so the unique
    # (workspace_id, customer_id, item) constraint never sees two rows for one dish.
    gone = [w.id for item, w in existing.items() if item not in wanted]
    if gone:
        session.exec(delete(PotWatch).where(PotWatch.id.in_(gone)))
    now = utcnow()
    for item in wanted:
        watch = existing.get(item)
        if watch is None:
            session.add(
                PotWatch(
                    workspace_id=workspace.id, customer_id=customer.id, item=item, phone=normalised
                )
            )
        elif watch.phone != normalised:
            watch.phone = normalised
            watch.updated_at = now
            session.add(watch)
    session.commit()
    return _watches(session, workspace=workspace, customer=customer)


def clear_watches(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Stop all alerts for this customer at this stand."""
    _delete_watches(session, workspace=workspace, customer=customer)
    session.commit()


def _delete_watches(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    session.exec(
        delete(PotWatch).where(
            PotWatch.workspace_id == workspace.id, PotWatch.customer_id == customer.id
        )
    )


def my_watch(session: Session, *, workspace: Workspace, customer: Customer) -> dict | None:
    """The customer's own dishes and their masked number, or None if they watch nothing."""
    watches = _watches(session, workspace=workspace, customer=customer)
    if not watches:
        return None
    return {"items": [w.item for w in watches], "phone_masked": mask_phone(watches[0].phone)}


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's pot_alert data at this stand (called by "Delete my data").

    The DELETE runs now, in the caller's transaction; the caller commits.
    """
    _delete_watches(session, workspace=workspace, customer=customer)


# --- Vendor: ready calls -------------------------------------------------------------------


def live_ready(
    session: Session, *, workspace: Workspace, now: datetime | None = None
) -> list[PotReady]:
    """Ready calls still showing: not ended and less than READY_WINDOW old, newest first."""
    since = (now or utcnow()) - READY_WINDOW
    return list(
        session.exec(
            select(PotReady)
            .where(
                PotReady.workspace_id == workspace.id,
                PotReady.ended == False,
                PotReady.created_at > since,
            )
            .order_by(PotReady.created_at.desc(), PotReady.id.desc())
        ).all()
    )


def ready_view(ready: PotReady) -> dict[str, Any]:
    return {
        "id": ready.id,
        "item": ready.item,
        "plates_left": ready.plates_left,
        "at": ready.created_at,
        "until": ready.created_at + READY_WINDOW,
    }


def mark_ready(
    session: Session, *, workspace: Workspace, item: str, plates_left: int | None = None
) -> PotReady:
    """The vendor's "Ready now". A new call for a dish replaces that dish's earlier live call."""
    name = _menu_name(menu_items(session, workspace=workspace), item)
    if plates_left is not None and not 1 <= plates_left <= MAX_PLATES_LEFT:
        raise PotAlertError(f"Plates left must be between 1 and {MAX_PLATES_LEFT}")
    for old in live_ready(session, workspace=workspace):
        if old.item == name:
            old.ended = True
            session.add(old)
    ready = PotReady(workspace_id=workspace.id, item=name, plates_left=plates_left)
    session.add(ready)
    session.commit()
    session.refresh(ready)
    return ready


def get_ready(session: Session, *, workspace: Workspace, ready_id: int) -> PotReady | None:
    return session.exec(
        select(PotReady).where(PotReady.id == ready_id, PotReady.workspace_id == workspace.id)
    ).first()


def end_ready(session: Session, *, ready: PotReady) -> PotReady:
    """Sold out: the banner goes away for everyone."""
    if not ready.ended:
        ready.ended = True
        ready.updated_at = utcnow()
        session.add(ready)
        session.commit()
        session.refresh(ready)
    return ready


def watchers_for(session: Session, *, workspace: Workspace, item: str) -> list[dict[str, str]]:
    """Customers waiting for this dish: first name and phone. Vendor routes only."""
    rows = session.exec(
        select(PotWatch, Customer)
        .join(Customer, Customer.id == PotWatch.customer_id)
        .where(PotWatch.workspace_id == workspace.id, PotWatch.item == item)
        .order_by(PotWatch.created_at, PotWatch.id)
    ).all()
    return [{"name": c.first_name or "Guest", "phone": w.phone} for w, c in rows]


def demand(session: Session, *, workspace: Workspace) -> list[dict[str, Any]]:
    """How many customers wait for each menu dish (0 included), in menu order."""
    counts = dict(
        session.exec(
            select(PotWatch.item, func.count(PotWatch.id))
            .where(PotWatch.workspace_id == workspace.id)
            .group_by(PotWatch.item)
        ).all()
    )
    return [
        {"item": item, "waiting": int(counts.get(item, 0))}
        for item in menu_items(session, workspace=workspace)
    ]


# --- Views ---------------------------------------------------------------------------------


def public_view(
    session: Session, *, workspace: Workspace, customer: Customer | None, enabled: bool
) -> dict[str, Any]:
    """What any phone may see. Never contains a phone number except the customer's own, masked."""
    if not enabled:
        return {"enabled": False, "items": [], "ready": [], "my": None}
    return {
        "enabled": True,
        "items": menu_items(session, workspace=workspace),
        "ready": [ready_view(r) for r in live_ready(session, workspace=workspace)],
        "my": my_watch(session, workspace=workspace, customer=customer) if customer else None,
    }


def vendor_view(session: Session, *, workspace: Workspace, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "stand_name": workspace.name,
        "slug": workspace.slug,
        "demand": demand(session, workspace=workspace),
        "ready": [ready_view(r) for r in live_ready(session, workspace=workspace)],
    }
