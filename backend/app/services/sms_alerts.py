"""Leftover-food alerts by text message (SMS through Termii): they reach every phone, iPhone and
Android, with no app and no notification settings.

The customer gives their number and agrees to the terms below on the stand page; the vendor's
"Tell my customers" (last plates) texts every number, at most once per ALERT_GAP_MINUTES (the same
limit as push alerts, see services/alerts.py). The vendor only ever sees how many numbers there
are, never the numbers. Delete-my-data removes the number.
"""

import logging
import re
from datetime import datetime

import requests
from sqlmodel import Session, select

from ..core.config import CustomaSettings, settings
from ..models import Character, Customer, SmsSubscription, Workspace

logger = logging.getLogger("customa.sms")

# What the customer agrees to. Change the version when the wording changes.
TERMS_VERSION = "2026-10-14"
TERMS = (
    "I agree to get text messages from {stand} through Customa when they have food left before "
    "closing. At most one text an hour, only when {stand} sends one. My number is never shown to "
    "the vendor. I can stop texts or delete my data on this page at any time."
)

# Termii's bulk endpoint takes many numbers per request; keep requests small and quick.
CHUNK = 100
SMS_LIMIT = 160  # one SMS page (plain GSM-7 text)
_NIGERIAN_MOBILE = re.compile(r"^234[789][01]\d{8}$")


class SmsError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sms_available() -> bool:
    return bool(settings.TERMII_API_KEY and settings.TERMII_SENDER_ID)


def terms_text(workspace: Workspace) -> str:
    return TERMS.format(stand=workspace.name)


def normalize_phone(raw: str) -> str | None:
    """A Nigerian mobile number as international digits ("2348031234567"), or None.

    Accepts 08031234567, 8031234567, +234 803 123 4567, 2348031234567 and 234 0803...
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "234" + digits[1:]
    elif len(digits) == 10:
        digits = "234" + digits
    elif len(digits) == 14 and digits.startswith("2340"):
        digits = "234" + digits[4:]
    return digits if _NIGERIAN_MOBILE.match(digits) else None


def masked(phone: str) -> str:
    """'0803 ••• 4567': enough for the customer to recognise their number."""
    return f"0{phone[3:6]} ••• {phone[-4:]}"


# --- Subscriptions -------------------------------------------------------------------------


def number_for(session: Session, *, workspace: Workspace, customer: Customer) -> SmsSubscription | None:
    return session.exec(
        select(SmsSubscription).where(
            SmsSubscription.workspace_id == workspace.id, SmsSubscription.customer_id == customer.id
        )
    ).first()


def subscribe(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    phone: str,
    stand_settings: CustomaSettings,
    now: datetime,
) -> SmsSubscription:
    if not sms_available():
        raise SmsError("Text alerts are not available yet.")
    number = normalize_phone(phone)
    if number is None:
        raise SmsError("That doesn't look like a Nigerian phone number. Try like 0803 123 4567.")

    row = number_for(session, workspace=workspace, customer=customer)
    # The same number on another card at this stand (a new phone or cleared browser): it moves here.
    other = session.exec(
        select(SmsSubscription).where(
            SmsSubscription.workspace_id == workspace.id,
            SmsSubscription.phone == number,
            SmsSubscription.customer_id != customer.id,
        )
    ).first()
    if other is not None:
        session.delete(other)
        session.flush()
    elif row is None and subscriber_count(session, workspace=workspace) >= stand_settings.SMS_MAX_SUBSCRIBERS:
        raise SmsError("This stand's text alerts are full right now.")

    if row is None:
        row = SmsSubscription(
            workspace_id=workspace.id, customer_id=customer.id, phone=number,
            agreed_at=now, terms_version=TERMS_VERSION,
        )
    else:
        row.phone, row.agreed_at, row.terms_version = number, now, TERMS_VERSION
    session.add(row)
    session.commit()
    return row


def unsubscribe(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    row = number_for(session, workspace=workspace, customer=customer)
    if row is not None:
        session.delete(row)
        session.commit()


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: the number is removed (the caller commits)."""
    row = number_for(session, workspace=workspace, customer=customer)
    if row is not None:
        session.delete(row)
        session.flush()


def subscriber_count(session: Session, *, workspace: Workspace) -> int:
    return len(session.exec(select(SmsSubscription.id).where(SmsSubscription.workspace_id == workspace.id)).all())


def numbers(session: Session, *, workspace: Workspace) -> list[str]:
    return list(session.exec(select(SmsSubscription.phone).where(SmsSubscription.workspace_id == workspace.id)).all())


# --- The text ------------------------------------------------------------------------------


def plain(text: str) -> str:
    """Plain text only: an emoji or curly quote would make the SMS cost more (Unicode pages)."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^A-Za-z0-9 .,'!?&()\-:/@]", "", text).strip()


def last_plates_text(
    *, workspace: Workspace, character: Character | None, plates_left: int, until_label: str
) -> str:
    """One SMS page, in the character's voice, with the link to the stand page."""
    first = plain((character.name if character else workspace.name).split(" ")[0]) or "Hi"
    stand = plain(workspace.name) or "your food spot"
    plates = f"{plates_left} plate{'' if plates_left == 1 else 's'}"
    link = f"{settings.PUBLIC_WEB_URL.split('://', 1)[-1].rstrip('/')}/s/{workspace.slug}"
    tail = f": last plates tonight! Only {plates} left. Come before {until_label}. {link}"
    room = SMS_LIMIT - len(tail) - len(first) - len(" at ")
    if len(stand) > room:
        stand = stand[: max(0, room - 1)].rstrip() + "."
    return f"{first} at {stand}{tail}"[:SMS_LIMIT]


def send_chunk(chunk: list[str], text: str) -> int:
    """Text up to CHUNK numbers in one Termii bulk request. Returns how many Termii accepted."""
    try:
        r = requests.post(
            f"{settings.TERMII_BASE_URL.rstrip('/')}/api/sms/send/bulk",
            json={
                "api_key": settings.TERMII_API_KEY,
                "to": chunk,
                "from": settings.TERMII_SENDER_ID,
                "sms": text,
                "type": "plain",
                "channel": settings.TERMII_CHANNEL,
            },
            timeout=10,
        )
    except requests.RequestException:
        logger.exception("Termii request failed")
        return 0
    if r.status_code == 200:
        return len(chunk)
    logger.warning("Termii refused %s numbers: %s %s", len(chunk), r.status_code, r.text[:300])
    return 0


def chunks(numbers_to_text: list[str]) -> list[list[str]]:
    return [numbers_to_text[i : i + CHUNK] for i in range(0, len(numbers_to_text), CHUNK)]
