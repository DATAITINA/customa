"""Leftover-food alerts: a push notification to customers' phones when the vendor announces
"last plates", written in the stand character's voice.

Web push (VAPID): works in Chrome, Edge, Firefox and Samsung Internet on Android, and on iPhone
(iOS 16.4+) when Customa is added to the Home Screen. The phone's service worker (frontend
public/sw.js) draws the notification with the character's picture.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from py_vapid import Vapid02
from pywebpush import WebPushException, webpush
from sqlmodel import Session, select

from ..core.config import CustomaSettings, settings
from ..models import Character, Customer, PushSubscription, Workspace
from .character_chat import NIGERIA
from .stands import set_stand_setting

logger = logging.getLogger("customa.alerts")

# Only real browser push services: the server posts to this URL, so nothing else is accepted.
PUSH_HOSTS = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
    ".push.apple.com",
    ".notify.windows.com",
)
SEND_DEADLINE_SECONDS = 15
_pool = ThreadPoolExecutor(max_workers=8)


class AlertError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def alerts_available() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def is_push_endpoint(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return any(host == h or (h.startswith(".") and host.endswith(h)) for h in PUSH_HOSTS)


# --- Subscriptions -------------------------------------------------------------------------


def subscribe(
    session: Session, *, workspace: Workspace, customer: Customer, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    if not alerts_available():
        raise AlertError("Alerts are not available yet.")
    if not is_push_endpoint(endpoint):
        raise AlertError("This browser's push service is not supported.")
    row = session.exec(
        select(PushSubscription).where(
            PushSubscription.workspace_id == workspace.id, PushSubscription.endpoint == endpoint
        )
    ).first()
    if row is None:
        row = PushSubscription(workspace_id=workspace.id, customer_id=customer.id, endpoint=endpoint, p256dh=p256dh, auth=auth)
    else:
        row.customer_id, row.p256dh, row.auth = customer.id, p256dh, auth
    session.add(row)
    session.commit()
    return row


def unsubscribe(session: Session, *, workspace: Workspace, customer: Customer, endpoint: str) -> None:
    row = session.exec(
        select(PushSubscription).where(
            PushSubscription.workspace_id == workspace.id,
            PushSubscription.customer_id == customer.id,
            PushSubscription.endpoint == endpoint,
        )
    ).first()
    if row is not None:
        session.delete(row)
        session.commit()


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: this customer's phones stop getting this stand's alerts."""
    for row in session.exec(
        select(PushSubscription).where(
            PushSubscription.workspace_id == workspace.id, PushSubscription.customer_id == customer.id
        )
    ).all():
        session.delete(row)
    session.flush()


def subscriber_count(session: Session, *, workspace: Workspace) -> int:
    return len(session.exec(select(PushSubscription.id).where(PushSubscription.workspace_id == workspace.id)).all())


# --- The alert ------------------------------------------------------------------------------


def nigeria_time(utc_iso: str) -> str:
    """'8:30 PM' in Nigeria time, from a naive UTC ISO time."""
    t = datetime.fromisoformat(utc_iso) + NIGERIA
    return t.strftime("%I:%M %p").lstrip("0")


def last_plates_message(
    *, workspace: Workspace, character: Character | None, plates_left: int, until: str
) -> dict[str, Any]:
    """The notification, in the character's voice. The phone draws it (frontend public/sw.js)."""
    name = character.name if character else workspace.name
    first = name.split(" ")[0]
    stand = workspace.name
    plates = f"{plates_left} plate{'' if plates_left == 1 else 's'}"
    return {
        "type": "last_plates",
        "slug": workspace.slug,
        "stand": stand,
        "title": f"{first}: last plates tonight! 🍲",
        "body": f"Only {plates} left at {stand}. Come chop before {nigeria_time(until)} 🏃🏾",
        "plates_left": plates_left,
        "until": until,
        "url": f"/s/{workspace.slug}",
        "tag": f"last-plates-{workspace.slug}",
        "character": {
            "name": name,
            "body": str(getattr(character.body, "value", character.body)) if character else "pepper",
            "color": character.color if character else "pepper",
            "accessory": character.accessory if character else "headwrap",
        },
    }


def _send_one(sub: dict[str, Any], payload: str, ttl: int) -> int | None:
    """Send to one phone. Returns the push service's status code on failure, None on success."""
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=payload,
            vapid_private_key=Vapid02.from_raw(settings.VAPID_PRIVATE_KEY.encode()),
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=ttl,
            timeout=8,
            headers={"Urgency": "high"},
        )
        return None
    except WebPushException as exc:
        return exc.response.status_code if exc.response is not None else 0
    except Exception:
        logger.exception("push to one phone failed")
        return 0


def send_last_plates(
    session: Session,
    *,
    workspace: Workspace,
    character: Character | None,
    stand_settings: CustomaSettings,
    plates_left: int,
    until: str,
    now: datetime,
) -> dict[str, Any]:
    """Alert every subscribed phone, at most once per ALERT_GAP_MINUTES per stand.

    Returns {"sent": n, "skipped": reason or None}. Phones that unsubscribed (404/410 from the
    push service) are removed.
    """
    if not alerts_available():
        return {"sent": 0, "skipped": "unavailable"}
    last = stand_settings.LAST_PLATES_ALERTED_AT
    if last and now - datetime.fromisoformat(last) < timedelta(minutes=stand_settings.ALERT_GAP_MINUTES):
        return {"sent": 0, "skipped": "recently_alerted"}
    # Plain values for the sending threads (they never touch the database session).
    subs = [
        {"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}
        for s in session.exec(select(PushSubscription).where(PushSubscription.workspace_id == workspace.id)).all()
    ]
    if not subs:
        return {"sent": 0, "skipped": "no_subscribers"}

    set_stand_setting(session, workspace, "LAST_PLATES_ALERTED_AT", now.isoformat(timespec="seconds"))
    message = last_plates_message(workspace=workspace, character=character, plates_left=plates_left, until=until)
    payload = json.dumps(message)
    # Drop the alert if a phone is offline until the announcement is over.
    ttl = max(60, int((datetime.fromisoformat(until) - now).total_seconds()))
    futures = {_pool.submit(_send_one, sub, payload, ttl): sub for sub in subs}
    done, _ = wait(futures, timeout=SEND_DEADLINE_SECONDS)
    sent = 0
    for future in done:
        status = future.result()
        if status is None:
            sent += 1
        elif status in (404, 410):
            gone = session.get(PushSubscription, futures[future]["id"])
            if gone is not None:
                session.delete(gone)
    session.commit()
    logger.info("last-plates alert for %s: %s of %s phones", workspace.slug, sent, len(subs))
    return {"sent": sent, "skipped": None}
