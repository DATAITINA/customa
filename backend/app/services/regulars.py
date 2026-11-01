"""Regular-arrived alert ("Ime don land!"): staff greet regulars by name, in person.

Every counted plate (a scan or "Use 1 prepaid plate") records an Arrival. The vendor dashboard
shows "Who's here now": the customers counted in the last ARRIVAL_WINDOW_MINUTES, each with their
first name (only if they gave it), which visit this is, when they last came, their jara status, a
greeting in the stand's voice and, only if the customer chose to share it, their usual. Staff tap
"Greeted" (saved, so greeting can be measured). A vendor's phone can also be pinged by web push
when a regular (2nd+ plate) arrives: at most once per visit; the dashboard works without it.

Privacy: no phone numbers, nothing from the private chat or ChatMemory. "Their usual" is only a
menu item the customer picked themselves, and clearing it or delete-my-data removes it.
"""

import json
import logging
from concurrent.futures import wait
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, func, select

from ..actions import visit_action
from ..core.config import CustomaSettings
from ..models import (
    Arrival,
    Character,
    Customer,
    CustomerUsual,
    JaraReward,
    VendorPushSubscription,
    Visit,
    Workspace,
)
from . import alerts
from .stands import resolve_stand_settings

logger = logging.getLogger("customa.regulars")
PING_DEADLINE_SECONDS = 4


class RegularsError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def ago(then: datetime | None, now: datetime) -> str | None:
    """'today', 'yesterday', '3 days ago', '2 weeks ago'."""
    if then is None:
        return None
    days = (now.date() - then.date()).days
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


# --- Recording arrivals ---------------------------------------------------------------------


def record_arrival(
    session: Session, *, workspace: Workspace, customer: Customer, visit: Visit, now: datetime
) -> Arrival:
    """Called for every counted plate (committed): which visit this is and when they last came."""
    visit_number = session.exec(select(func.count(Visit.id)).where(Visit.customer_id == customer.id)).one()
    previous = session.exec(
        select(Visit.created_at)
        .where(Visit.customer_id == customer.id, Visit.id != visit.id)
        .order_by(Visit.id.desc())
        .limit(1)
    ).first()
    arrival = Arrival(
        workspace_id=workspace.id,
        customer_id=customer.id,
        visit_id=visit.id,
        visit_number=visit_number,
        previous_at=previous,
    )
    session.add(arrival)
    session.commit()
    session.refresh(arrival)
    if visit_number >= 2:
        ping_vendor(session, workspace=workspace, customer=customer, arrival=arrival, now=now)
    return arrival


def _jara_status(session: Session, customer: Customer, stand_settings: CustomaSettings) -> str | None:
    """'has_jara' (an unredeemed jara code), 'next_is_jara' (their next own plate earns one)."""
    open_jara = session.exec(
        select(JaraReward.id).where(JaraReward.customer_id == customer.id, JaraReward.redeemed == False)
    ).first()
    if open_jara is not None:
        return "has_jara"
    own = visit_action.last_own_card_visit(session, customer_id=customer.id)
    if own is not None and own.plate_number % stand_settings.PLATES_FOR_JARA == stand_settings.PLATES_FOR_JARA - 1:
        return "next_is_jara"
    return None


def greeting(name: str | None, visit_number: int, jara: str | None) -> str:
    """What staff can say, in the stand's voice."""
    if visit_number <= 1:
        return f"Welcome{', ' + name if name else ''}! First time here? You go enjoy am 👋"
    hello = f"{name}! Welcome back o! 🙌" if name else "Welcome back o! Good to see you again 🙌"
    if visit_number >= 5:
        hello = f"Ah, {name}! Our regular! Welcome back o! 🙌" if name else "Our regular! Welcome back o! 🙌"
    if jara == "next_is_jara":
        hello += " Your next plate na jara!"
    elif jara == "has_jara":
        hello += " Your jara dey wait for you."
    return hello


def here_now(
    session: Session, *, workspace: Workspace, stand_settings: CustomaSettings, now: datetime
) -> list[dict[str, Any]]:
    """Customers counted in the last ARRIVAL_WINDOW_MINUTES, newest first."""
    since = now - timedelta(minutes=stand_settings.ARRIVAL_WINDOW_MINUTES)
    rows = session.exec(
        select(Arrival, Customer)
        .join(Customer, Customer.id == Arrival.customer_id)
        .where(Arrival.workspace_id == workspace.id, Arrival.created_at >= since)
        .order_by(Arrival.id.desc())
        .limit(12)
    ).all()
    seen: set[int] = set()
    out = []
    for arrival, customer in rows:
        if customer.id in seen:  # one entry per customer (their latest plate)
            continue
        seen.add(customer.id)
        name = customer.first_name or None
        jara = _jara_status(session, customer, stand_settings)
        usual = session.exec(select(CustomerUsual.item).where(CustomerUsual.customer_id == customer.id)).first()
        out.append(
            {
                "id": arrival.id,
                "name": name,
                "visit_number": arrival.visit_number,
                "visit_label": "New face: first plate 👋" if arrival.visit_number <= 1 else f"{ordinal(arrival.visit_number)} visit",
                "returning": arrival.visit_number >= 2,
                "last_came": ago(arrival.previous_at, now),
                "jara": jara,
                "greeting": greeting(name, arrival.visit_number, jara),
                "usual": usual,
                "at": arrival.created_at,
                "greeted_at": arrival.greeted_at,
            }
        )
    return out


def mark_greeted(session: Session, *, workspace: Workspace, arrival_id: int, now: datetime) -> Arrival:
    arrival = session.get(Arrival, arrival_id)
    if arrival is None or arrival.workspace_id != workspace.id:
        raise RegularsError(404, "No such arrival at this stand")
    if arrival.greeted_at is None:
        arrival.greeted_at = now
        session.add(arrival)
        session.commit()
        session.refresh(arrival)
    return arrival


# --- The vendor's phone ping (web push) -----------------------------------------------------


def vendor_subscribe(
    session: Session, *, workspace: Workspace, account_id: int, endpoint: str, p256dh: str, auth: str
) -> None:
    if not alerts.alerts_available():
        raise RegularsError(400, "Phone pings are not available yet.")
    if not alerts.is_push_endpoint(endpoint):
        raise RegularsError(400, "This browser's push service is not supported.")
    row = session.exec(
        select(VendorPushSubscription).where(
            VendorPushSubscription.workspace_id == workspace.id, VendorPushSubscription.endpoint == endpoint
        )
    ).first()
    if row is None:
        row = VendorPushSubscription(workspace_id=workspace.id, account_id=account_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
    else:
        row.account_id, row.p256dh, row.auth = account_id, p256dh, auth
    session.add(row)
    session.commit()


def vendor_unsubscribe(session: Session, *, workspace: Workspace, endpoint: str) -> None:
    for row in session.exec(
        select(VendorPushSubscription).where(
            VendorPushSubscription.workspace_id == workspace.id, VendorPushSubscription.endpoint == endpoint
        )
    ).all():
        session.delete(row)
    session.commit()


def vendor_phones(session: Session, *, workspace: Workspace) -> int:
    return session.exec(
        select(func.count(VendorPushSubscription.id)).where(VendorPushSubscription.workspace_id == workspace.id)
    ).one()


def ping_message(workspace: Workspace, customer: Customer, arrival: Arrival, jara: str | None, usual: str | None) -> dict[str, Any]:
    who = customer.first_name or "A regular"
    bits = [f"{ordinal(arrival.visit_number)} visit"]
    if arrival.previous_at is not None:
        bits.append(f"last came {ago(arrival.previous_at, arrival.created_at)}")
    if jara == "next_is_jara":
        bits.append("next plate is jara!")
    elif jara == "has_jara":
        bits.append("has a jara code")
    if usual:
        bits.append(f"usual: {usual}")
    return {
        "type": "regular_arrived",
        "slug": workspace.slug,
        "title": f"{who} don land! 🙌",
        "body": " · ".join(bits),
        "url": "/vendor",
        "tag": f"arrival-{arrival.id}",
    }


def ping_vendor(session: Session, *, workspace: Workspace, customer: Customer, arrival: Arrival, now: datetime) -> int:
    """Ping the vendor's phones that asked for it: returning customers only, once per visit."""
    if arrival.pinged_at is not None or not alerts.alerts_available():
        return 0
    subs = [
        {"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}
        for s in session.exec(
            select(VendorPushSubscription).where(VendorPushSubscription.workspace_id == workspace.id)
        ).all()
    ]
    if not subs:
        return 0
    jara = _jara_status(session, customer, resolve_stand_settings(session, workspace))
    usual = session.exec(select(CustomerUsual.item).where(CustomerUsual.customer_id == customer.id)).first()
    payload = json.dumps(ping_message(workspace, customer, arrival, jara, usual))
    arrival.pinged_at = now
    session.add(arrival)
    session.commit()
    futures = {alerts._pool.submit(alerts._send_one, sub, payload, 30 * 60): sub for sub in subs}
    done, _ = wait(futures, timeout=PING_DEADLINE_SECONDS)
    sent = 0
    for future in done:
        status = future.result()
        if status is None:
            sent += 1
        elif status in (404, 410):
            gone = session.get(VendorPushSubscription, futures[future]["id"])
            if gone is not None:
                session.delete(gone)
    session.commit()
    return sent


# --- "My usual", chosen by the customer -----------------------------------------------------


def menu_items(character: Character | None) -> list[str]:
    return [str(m.get("item", "")).strip() for m in (character.menu if character and character.menu else []) if m.get("item")]


def get_usual(session: Session, *, customer: Customer) -> str | None:
    return session.exec(select(CustomerUsual.item).where(CustomerUsual.customer_id == customer.id)).first()


def set_usual(session: Session, *, workspace: Workspace, customer: Customer, character: Character | None, item: str) -> str:
    choice = next((m for m in menu_items(character) if m.lower() == item.strip().lower()), None)
    if choice is None:
        raise RegularsError(400, "Pick something from the menu.")
    row = session.exec(select(CustomerUsual).where(CustomerUsual.customer_id == customer.id)).first()
    if row is None:
        row = CustomerUsual(workspace_id=workspace.id, customer_id=customer.id, item=choice)
    else:
        row.item = choice
    session.add(row)
    session.commit()
    return choice


def clear_usual(session: Session, *, customer: Customer) -> None:
    row = session.exec(select(CustomerUsual).where(CustomerUsual.customer_id == customer.id)).first()
    if row is not None:
        session.delete(row)
        session.commit()


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: arrivals and the usual (the caller commits)."""
    for model in (Arrival, CustomerUsual):
        for row in session.exec(select(model).where(model.customer_id == customer.id)).all():
            session.delete(row)
    session.flush()
