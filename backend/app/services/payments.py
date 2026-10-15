"""Pay for a plate: the customer pays on their phone (Paystack, test mode) or pays cash and the
vendor confirms it. A paid plate counts as a stamp through the one plate path
(plates.count_visit), so the 6-hour rule, jara and every booster still apply.

Rules:
- Off until the stand turns PAYMENTS_ENABLED on. Prices come from the stand's menu (server side).
- Cash: one pending cash payment per customer; the customer's screen shows a 3-letter code the
  vendor matches on the dashboard before tapping "Cash received".
- Paystack: paid only when Paystack's own verify says "success" for the exact amount, in NGN.
  The return page and the webhook may both confirm: a payment is marked paid once (atomic).
- A plate already counted in the last 6 hours: the payment is still paid, but no extra stamp.
- "Delete my data": pending payments go; paid ones stay as the vendor's takings, without the
  customer.
- Privacy: the vendor sees a first name only if given, never a phone number.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, select

from app.actions import PlateTooSoon
from app.actions.payments import payment_action
from app.core.config import CustomaSettings, settings
from app.models import Character, Customer, Payment, PaymentCreate, Workspace
from app.services import paystack
from app.services.plate_ajo import menu_items
from app.services.plates import count_visit

NIGERIA = timedelta(hours=1)
METHODS = ("paystack", "cash")


class PaymentError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def enabled(stand_settings: CustomaSettings) -> bool:
    return bool(stand_settings.PAYMENTS_ENABLED)


def view(p: Payment) -> dict[str, Any]:
    return {
        "id": p.id,
        "reference": p.reference,
        "method": p.method,
        "status": p.status,
        "item": p.item,
        "amount": p.amount_naira,
        "code": p.match_code,
        "stamped": p.visit_id is not None,
        "paid_at": p.paid_at,
    }


def _pending_cash(session: Session, customer: Customer) -> Payment | None:
    return payment_action.get_by_all(session, customer_id=customer.id, method="cash", status="pending")


def customer_state(session: Session, *, workspace: Workspace, customer: Customer | None,
                   character: Character | None, stand_settings: CustomaSettings) -> dict[str, Any]:
    """What the customer's "Pay for this plate" card shows."""
    on = enabled(stand_settings)
    menu = menu_items(character.menu if character else None) if on else []
    pending = _pending_cash(session, customer) if (on and customer) else None
    return {
        "enabled": on and bool(menu),
        "card": paystack.available(),
        "test_mode": True,
        "menu": menu,
        "pending_cash": view(pending) if pending else None,
    }


def _price(character: Character | None, item: str) -> int:
    for entry in menu_items(character.menu if character else None):
        if entry["item"] == item:
            return entry["price"]
    raise PaymentError("That item isn't on today's menu. Pick another one.", status=400)


def _new(session: Session, *, workspace: Workspace, customer: Customer, method: str, item: str, price: int) -> Payment:
    return payment_action.create(
        session,
        data=PaymentCreate(
            reference=f"cst_{workspace.id}_{secrets.token_hex(8)}",
            method=method,
            item=item,
            amount_naira=price,
            match_code="".join(secrets.choice(string.ascii_uppercase.replace("O", "").replace("I", "")) for _ in range(3)),
        ),
        update={"workspace_id": workspace.id, "customer_id": customer.id},
    )


def start(session: Session, *, workspace: Workspace, customer: Customer, character: Character | None,
          stand_settings: CustomaSettings, item: str, method: str) -> dict[str, Any]:
    """Start a payment. Paystack: returns the checkout URL. Cash: returns the code to show."""
    if not enabled(stand_settings):
        raise PaymentError("This stand doesn't take payments in Customa yet.", status=403)
    if method not in METHODS:
        raise PaymentError("Pick card/transfer or cash.")
    price = _price(character, item)
    if method == "cash":
        old = _pending_cash(session, customer)
        if old:
            payment_action.update(session, model=old, update={"status": "cancelled"})
        p = _new(session, workspace=workspace, customer=customer, method="cash", item=item, price=price)
        return {"payment": view(p), "checkout_url": None}

    problem = paystack.key_problem()
    if problem:
        raise PaymentError("Card payments aren't set up at this stand yet. You can pay cash.", status=503)
    p = _new(session, workspace=workspace, customer=customer, method="paystack", item=item, price=price)
    try:
        url = paystack.initialize(
            reference=p.reference,
            amount_kobo=price * 100,
            email=f"{p.reference}@{settings.PAYSTACK_EMAIL_DOMAIN}",
            callback_url=f"{settings.PUBLIC_WEB_URL.rstrip('/')}/s/{workspace.slug}/paid",
            metadata={"stand": workspace.slug, "item": item},
        )
    except paystack.PaystackError as exc:
        payment_action.update(session, model=p, update={"status": "failed"})
        raise PaymentError(exc.message, status=exc.status)
    return {"payment": view(p), "checkout_url": url}


def _mark_paid(session: Session, *, workspace: Workspace, payment: Payment, stand_settings: CustomaSettings,
               confirmed_by: int | None = None) -> bool:
    """Pending -> paid exactly once (safe when the webhook and the return page race), then count
    the plate as a stamp. Returns False when someone else already marked it."""
    claimed = session.exec(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status == "pending")
        .values(status="paid", paid_at=_now(), confirmed_by=confirmed_by, updated_at=_now())
    ).rowcount
    session.commit()
    session.refresh(payment)
    if not claimed or payment.customer_id is None:
        return False
    customer = session.get(Customer, payment.customer_id)
    try:
        visit = count_visit(session, workspace=workspace, customer=customer, stand_settings=stand_settings)
    except PlateTooSoon:
        return True  # paid, but this customer's plate was already counted in the last 6 hours
    payment_action.update(session, model=payment, update={"visit_id": visit.id})
    return True


def confirm_paystack(session: Session, *, workspace: Workspace, reference: str,
                     stand_settings: CustomaSettings) -> Payment:
    """Ask Paystack whether this payment went through; mark it paid (and stamp) if it did."""
    p = payment_action.by_reference(session, reference=reference)
    if p is None or p.workspace_id != workspace.id or p.method != "paystack":
        raise PaymentError("We can't find that payment.", status=404)
    if p.status != "pending":
        return p
    try:
        tx = paystack.verify(reference)
    except paystack.PaystackError as exc:
        raise PaymentError(exc.message, status=exc.status)
    status = tx.get("status")
    if status == "success":
        if tx.get("amount") != p.amount_naira * 100 or tx.get("currency") != "NGN":
            payment_action.update(session, model=p, update={"status": "failed"})
            raise PaymentError("The amount paid doesn't match the plate price. Ask the vendor.", status=409)
        _mark_paid(session, workspace=workspace, payment=p, stand_settings=stand_settings)
    elif status in ("failed", "abandoned", "reversed"):
        payment_action.update(session, model=p, update={"status": "failed"})
    session.refresh(p)
    return p


def confirm_cash(session: Session, *, workspace: Workspace, payment_id: int, account_id: int,
                 stand_settings: CustomaSettings) -> Payment:
    p = payment_action.get_by_all(session, id=payment_id, workspace_id=workspace.id, method="cash")
    if p is None:
        raise PaymentError("That cash payment isn't waiting any more.", status=404)
    if p.status != "pending":
        raise PaymentError("That cash payment was already handled.", status=409)
    _mark_paid(session, workspace=workspace, payment=p, stand_settings=stand_settings, confirmed_by=account_id)
    session.refresh(p)
    return p


def cancel(session: Session, *, workspace: Workspace, payment_id: int, customer: Customer | None = None) -> None:
    filters: dict[str, Any] = {"id": payment_id, "workspace_id": workspace.id, "status": "pending"}
    if customer is not None:
        filters["customer_id"] = customer.id
    p = payment_action.get_by_all(session, **filters)
    if p is None:
        raise PaymentError("That payment isn't waiting any more.", status=404)
    payment_action.update(session, model=p, update={"status": "cancelled"})


def today(session: Session, *, workspace: Workspace, now: datetime | None = None) -> dict[str, Any]:
    """The vendor's "Today's payments" (Nigeria day): totals by method and the list, plus cash
    payments waiting for "Cash received"."""
    now = now or _now()
    start_of_day = (now + NIGERIA).replace(hour=0, minute=0, second=0, microsecond=0) - NIGERIA
    rows = payment_action.for_workspace_since(session, workspace_id=workspace.id, since=start_of_day)
    names = {
        c.id: c.first_name
        for c in session.exec(select(Customer).where(Customer.id.in_({r.customer_id for r in rows if r.customer_id}))).all()
    } if rows else {}
    paid = [r for r in rows if r.status == "paid"]
    by_method = {m: sum(r.amount_naira for r in paid if r.method == m) for m in METHODS}

    def row(r: Payment) -> dict[str, Any]:
        return {**view(r), "name": names.get(r.customer_id) or "A customer", "at": r.paid_at or r.created_at}

    return {
        "total": sum(by_method.values()),
        "count": len(paid),
        "by_method": by_method,
        "paid": [row(r) for r in paid[:30]],
        "waiting_cash": [row(r) for r in rows if r.method == "cash" and r.status == "pending"],
        "card_ready": paystack.available(),
        "card_problem": paystack.key_problem(),
    }


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    for p in payment_action.get_multi_by_expressions(session, Payment.customer_id == customer.id, limit=None):
        if p.status == "pending":
            payment_action.delete(session, p.id)
        else:
            payment_action.update(session, model=p, update={"customer_id": None, "visit_id": None})
