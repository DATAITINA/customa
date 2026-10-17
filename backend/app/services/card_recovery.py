"""Customer card recovery: link a card to a phone number, get it back in any browser.

Why: a customer is known by a key kept in one browser's storage. Another browser, an in-app
browser (WhatsApp, a QR scanner), a private tab or the iPhone Home Screen app has no key, so the
customer looked new. Now a customer can link their card to their number with a 4-digit PIN, and
any browser that proves the card is theirs gets its own key for the same customer.

Proof of ownership (no MSFLib module does OTP or phone checks; hashing and code generation come
from msflib.core.security and msflib.utils.random):
- always: the 4-digit PIN chosen when linking (bcrypt hash, never stored in plain text);
- when the stand can send texts (Termii set up): a 6-digit SMS code, valid 10 minutes, as a
  second way in for a customer who forgot their PIN.

Security rules:
- The number is never stored: only a keyed hash (lookup) and a masked form (display).
- Never reveal whether a number has a card: unknown numbers get the same answers, the same
  timing (a dummy bcrypt check) and count towards the same lockouts.
- Lockout: RECOVERY_MAX_WRONG wrong tries for a number lock it for RECOVERY_LOCK_MINUTES;
  RECOVERY_DAY_MAX_WRONG in 24 hours lock it for the day. Each browser/network (IP) is limited
  too, so nobody can try one PIN on many numbers.
- Every attempt is logged (RecoveryAttempt), success or not.
- A number links to one card per stand; linking never moves a number from another card.
- Anti-cheat is unchanged: the 6-hour window is per customer, and a plate counted on the card
  this browser had before recovering still holds the window (see check_previous_cards).
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from msflib.core.security import get_password_hash, verify_password
from msflib.utils.random import random_digits
from sqlmodel import Session, select

from app.actions import PlateTooSoon
from app.actions.card_recovery import (
    customer_phone_action,
    device_key_action,
    recovery_attempt_action,
    recovery_code_action,
)
from app.core.config import CustomaSettings, settings
from app.models import (
    Customer,
    CustomerDeviceKey,
    CustomerDeviceKeyCreate,
    CustomerPhoneCreate,
    RecoveryAttempt,
    RecoveryAttemptCreate,
    RecoveryCode,
    RecoveryCodeCreate,
    Visit,
    Workspace,
)
from app.services import sms_alerts

RECOVERY_MAX_WRONG = 5
RECOVERY_LOCK_MINUTES = 30
RECOVERY_DAY_MAX_WRONG = 15
IP_HOUR_MAX_WRONG = 20
CODE_MINUTES = 10
SMS_PER_NUMBER_PER_HOUR = 3


def _secret(value: str) -> str:
    """PINs and codes are peppered with the app secret before bcrypt, so a copy of the database
    alone is not enough to try all 10,000 PINs."""
    return hmac.new(settings.SECRET_KEY.encode(), f"pin:{value}".encode(), hashlib.sha256).hexdigest()


def _hash(value: str) -> str:
    return get_password_hash(_secret(value))


def _matches(value: str, hashed: str) -> bool:
    return verify_password(_secret(value), hashed)


# A real bcrypt hash of a random PIN: checked when a number is unknown, so it takes as long.
_DUMMY_HASH = _hash(secrets.token_hex(8))
WRONG = ("wrong", "locked", "limited")


class RecoveryError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


NO_MATCH = "That number and PIN don't match a card here. Check them and try again."
NO_CODE_MATCH = "That code doesn't match or has expired. Check it or ask for a new one."
LOCKED = "Too many tries for this number. For your safety, try again in {minutes} minutes."
LIMITED = "Too many tries from this phone. Wait a little and try again."


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def enabled(stand_settings: CustomaSettings) -> bool:
    return bool(stand_settings.CARD_RECOVERY_ENABLED)


def phone_hash(workspace: Workspace, phone: str) -> str:
    """Keyed hash of the number for this stand: the number itself is never stored."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{workspace.id}:{phone}".encode(), hashlib.sha256).hexdigest()


def ip_hash(ip: str | None) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"ip:{ip or '-'}".encode(), hashlib.sha256).hexdigest()[:32]


def _normalize(raw: str) -> str:
    phone = sms_alerts.normalize_phone(raw)
    if phone is None:
        raise RecoveryError("Enter a Nigerian mobile number, like 0803 123 4567.")
    return phone


def _check_pin_shape(pin: str) -> str:
    pin = (pin or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        raise RecoveryError("Your PIN is 4 numbers, like 2580.")
    if pin in {"0000", "1111", "1234", "4321", "2222", "9999"} or len(set(pin)) == 1:
        raise RecoveryError("That PIN is too easy to guess. Pick 4 numbers only you know.")
    return pin


def _log(session: Session, workspace: Workspace, *, ph: str, ip: str, kind: str, outcome: str,
         customer_id: int | None = None) -> None:
    recovery_attempt_action.create(
        session,
        data=RecoveryAttemptCreate(phone_hash=ph, ip_hash=ip, kind=kind, outcome=outcome, customer_id=customer_id),
        update={"workspace_id": workspace.id},
    )


def _guard(session: Session, workspace: Workspace, *, ph: str, ip: str, kind: str) -> None:
    """Raise (and log) when this number is locked or this IP has tried too often."""
    now = _now()
    wrong_number = {"workspace_id": workspace.id, "phone_hash": ph}
    if recovery_attempt_action.count(session, since=now - timedelta(hours=24), outcomes=("wrong",), **wrong_number) >= RECOVERY_DAY_MAX_WRONG:
        _log(session, workspace, ph=ph, ip=ip, kind=kind, outcome="locked")
        raise RecoveryError(LOCKED.format(minutes=24 * 60), status=429)
    if recovery_attempt_action.count(session, since=now - timedelta(minutes=RECOVERY_LOCK_MINUTES), outcomes=("wrong",), **wrong_number) >= RECOVERY_MAX_WRONG:
        _log(session, workspace, ph=ph, ip=ip, kind=kind, outcome="locked")
        raise RecoveryError(LOCKED.format(minutes=RECOVERY_LOCK_MINUTES), status=429)
    if recovery_attempt_action.count(session, since=now - timedelta(hours=1), outcomes=WRONG, ip_hash=ip) >= IP_HOUR_MAX_WRONG:
        _log(session, workspace, ph=ph, ip=ip, kind=kind, outcome="limited")
        raise RecoveryError(LIMITED, status=429)


# --- Link ----------------------------------------------------------------------------------


def state(session: Session, *, customer: Customer | None, stand_settings: CustomaSettings) -> dict[str, Any]:
    link = customer_phone_action.for_customer(session, customer_id=customer.id) if customer else None
    return {
        "enabled": enabled(stand_settings),
        "linked": link is not None,
        "masked": link.phone_masked if link else None,
        "sms": sms_alerts.sms_available(),
    }


def link(session: Session, *, workspace: Workspace, customer: Customer, stand_settings: CustomaSettings,
         phone_raw: str, pin: str, ip: str | None) -> dict[str, Any]:
    """Save this card under a number + PIN (or change them). Optional for the customer."""
    if not enabled(stand_settings):
        raise RecoveryError("Saving cards is off at this stand.", status=403)
    phone = _normalize(phone_raw)
    pin = _check_pin_shape(pin)
    ph, iph = phone_hash(workspace, phone), ip_hash(ip)
    _guard(session, workspace, ph=ph, ip=iph, kind="link")
    owner = customer_phone_action.by_hash(session, workspace_id=workspace.id, phone_hash=ph)
    if owner is not None and owner.customer_id != customer.id:
        # Never move a number from someone else's card. The message also fits a customer who
        # simply saved it on another browser, so it says little about the number.
        _log(session, workspace, ph=ph, ip=iph, kind="link", outcome="taken", customer_id=customer.id)
        raise RecoveryError(
            "We can't save this number on this card. If you saved it before, use \"Already have a card?\" to get that card back.",
            status=409,
        )
    mine = customer_phone_action.for_customer(session, customer_id=customer.id)
    values = {"phone_hash": ph, "phone_masked": sms_alerts.masked(phone), "pin_hash": _hash(pin)}
    if mine:
        customer_phone_action.update(session, model=mine, update=values)
    else:
        customer_phone_action.create(session, data=CustomerPhoneCreate(**values),
                                     update={"workspace_id": workspace.id, "customer_id": customer.id})
    _log(session, workspace, ph=ph, ip=iph, kind="link", outcome="ok", customer_id=customer.id)
    return state(session, customer=customer, stand_settings=stand_settings)


def unlink(session: Session, *, customer: Customer, stand_settings: CustomaSettings) -> dict[str, Any]:
    mine = customer_phone_action.for_customer(session, customer_id=customer.id)
    if mine:
        customer_phone_action.delete(session, mine.id)
    return state(session, customer=customer, stand_settings=stand_settings)


# --- Recover -------------------------------------------------------------------------------


def send_code(session: Session, *, workspace: Workspace, stand_settings: CustomaSettings,
              phone_raw: str, ip: str | None) -> dict[str, Any]:
    """Text a 6-digit code to the number if it has a card here. The answer is the same either
    way, so it never tells whether the number has a card."""
    if not enabled(stand_settings) or not sms_alerts.sms_available():
        raise RecoveryError("Text codes aren't available at this stand. Use your PIN.", status=503)
    phone = _normalize(phone_raw)
    ph, iph = phone_hash(workspace, phone), ip_hash(ip)
    _guard(session, workspace, ph=ph, ip=iph, kind="sms_send")
    answer = {"sent": True, "message": "If this number has a card here, a 6-digit code is on its way by text."}
    recent = recovery_attempt_action.count(session, since=_now() - timedelta(hours=1), outcomes=("sent", "skipped"),
                                           workspace_id=workspace.id, phone_hash=ph)
    if recent >= SMS_PER_NUMBER_PER_HOUR:
        raise RecoveryError("We sent a few codes already. Wait a little, or use your PIN.", status=429)
    if customer_phone_action.by_hash(session, workspace_id=workspace.id, phone_hash=ph) is None:
        _log(session, workspace, ph=ph, ip=iph, kind="sms_send", outcome="skipped")
        return answer
    code = random_digits(6)
    recovery_code_action.create(
        session,
        data=RecoveryCodeCreate(phone_hash=ph, code_hash=_hash(code), expires_at=_now() + timedelta(minutes=CODE_MINUTES)),
        update={"workspace_id": workspace.id},
    )
    text = sms_alerts.plain(f"Your {workspace.name} card code is {code}. It works for {CODE_MINUTES} minutes. Don't share it.")
    sms_alerts.send_chunk([phone], text)
    _log(session, workspace, ph=ph, ip=iph, kind="sms_send", outcome="sent")
    return answer


def recover(session: Session, *, workspace: Workspace, stand_settings: CustomaSettings, phone_raw: str,
            pin: str | None, code: str | None, current: Customer | None, ip: str | None) -> tuple[Customer, str]:
    """Prove the card is yours (PIN or SMS code); this browser gets a fresh key for that card.
    Returns (customer, new key)."""
    if not enabled(stand_settings):
        raise RecoveryError("Getting a card back is off at this stand.", status=403)
    phone = _normalize(phone_raw)
    ph, iph = phone_hash(workspace, phone), ip_hash(ip)
    kind = "sms_code" if code else "pin"
    _guard(session, workspace, ph=ph, ip=iph, kind=kind)
    link_row = customer_phone_action.by_hash(session, workspace_id=workspace.id, phone_hash=ph)

    if code:
        live = recovery_code_action.live(session, workspace_id=workspace.id, phone_hash=ph, now=_now())
        ok = _matches(code.strip(), live.code_hash if live else _DUMMY_HASH) and live is not None and link_row is not None
        if ok:
            recovery_code_action.update(session, model=live, update={"used_at": _now()})
    else:
        ok = _matches((pin or "").strip(), link_row.pin_hash if link_row else _DUMMY_HASH) and link_row is not None

    if not ok:
        _log(session, workspace, ph=ph, ip=iph, kind=kind, outcome="wrong")
        raise RecoveryError(NO_CODE_MATCH if code else NO_MATCH)

    customer = session.get(Customer, link_row.customer_id)
    key = secrets.token_urlsafe(16)
    came_from = current.id if current is not None and current.id != customer.id else None
    device_key_action.create(session, data=CustomerDeviceKeyCreate(key=key, came_from_customer_id=came_from),
                             update={"workspace_id": workspace.id, "customer_id": customer.id})
    _log(session, workspace, ph=ph, ip=iph, kind=kind, outcome="ok", customer_id=customer.id)
    object.__setattr__(customer, "_presented_key", key)
    return customer, key


# --- Anti-cheat and privacy ----------------------------------------------------------------


def check_previous_cards(session: Session, *, customer: Customer, window_seconds: int) -> None:
    """A browser that counted a plate on another card, then recovered this one, still waits out
    the window: recovery never gives an extra plate inside it."""
    previous = device_key_action.previous_cards(session, customer_id=customer.id)
    if not previous:
        return
    last = session.exec(select(Visit).where(Visit.customer_id.in_(previous)).order_by(Visit.created_at.desc()).limit(1)).first()
    if last is not None:
        next_allowed = last.created_at + timedelta(seconds=window_seconds)
        now = _now()
        if now < next_allowed:
            raise PlateTooSoon(seconds_left=int((next_allowed - now).total_seconds()) + 1)


def saved_ids(session: Session, customer_ids: set[int]) -> set[int]:
    """Customers who saved their card (for the vendor's small "saved" mark; never the number)."""
    return customer_phone_action.linked_ids(session, customer_ids=customer_ids)


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """"Delete my data": the number link, this card's extra keys and its log rows go."""
    mine = customer_phone_action.for_customer(session, customer_id=customer.id)
    if mine:
        for code_row in recovery_code_action.get_multi_by_expressions(
            session, RecoveryCode.workspace_id == workspace.id, RecoveryCode.phone_hash == mine.phone_hash, limit=None
        ):
            recovery_code_action.delete(session, code_row.id, commit=False)
        customer_phone_action.delete(session, mine.id, commit=False)
    for d in device_key_action.get_multi_by_expressions(session, CustomerDeviceKey.customer_id == customer.id, limit=None):
        device_key_action.delete(session, d.id, commit=False)
    for d in device_key_action.get_multi_by_expressions(session, CustomerDeviceKey.came_from_customer_id == customer.id, limit=None):
        device_key_action.update(session, model=d, update={"came_from_customer_id": None}, commit=False)
    for a in recovery_attempt_action.get_multi_by_expressions(session, RecoveryAttempt.customer_id == customer.id, limit=None):
        recovery_attempt_action.update(session, model=a, update={"customer_id": None}, commit=False)
    session.commit()
