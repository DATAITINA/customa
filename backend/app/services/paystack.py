"""Paystack client, TEST MODE ONLY: start a payment, check it, and check a webhook's signature.

Only a secret key starting with sk_test_ is used; a live key is refused (no real money moves).
Every failure raises PaystackError with a message a person can act on.
"""

import hashlib
import hmac
import logging
from typing import Any

import requests

from app.core.config import settings

log = logging.getLogger(__name__)
TIMEOUT = 15


class PaystackError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def key_problem() -> str | None:
    """Why Paystack can't be used right now, or None when a test key is set."""
    key = (settings.PAYSTACK_SECRET_KEY or "").strip()
    if not key:
        return "Card payments are not set up yet (PAYSTACK_SECRET_KEY is missing)."
    if key.startswith("sk_live_"):
        return "A live Paystack key was set. Customa runs Paystack in test mode only: use an sk_test_ key."
    if not key.startswith("sk_test_"):
        return "PAYSTACK_SECRET_KEY doesn't look like a Paystack test secret key (sk_test_...)."
    return None


def available() -> bool:
    return key_problem() is None


def _headers() -> dict[str, str]:
    problem = key_problem()
    if problem:
        raise PaystackError(problem, status=503)
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY.strip()}", "Content-Type": "application/json"}


def _call(method: str, path: str, **kwargs) -> dict[str, Any]:
    headers = _headers()
    try:
        r = requests.request(method, f"{settings.PAYSTACK_BASE_URL.rstrip('/')}{path}", headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("Paystack %s %s failed: %s", method, path, exc)
        raise PaystackError("Couldn't reach Paystack. Check your connection and try again.")
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or not body.get("status"):
        log.warning("Paystack %s %s -> %s %s", method, path, r.status_code, body.get("message"))
        if r.status_code == 401:
            raise PaystackError("Paystack refused the key. Check PAYSTACK_SECRET_KEY (test key).", status=503)
        raise PaystackError(f"Paystack said: {body.get('message') or 'payment could not start'}.")
    return body.get("data") or {}


def initialize(*, reference: str, amount_kobo: int, email: str, callback_url: str, metadata: dict) -> str:
    """Start a payment; returns the Paystack checkout URL to send the customer to."""
    data = _call(
        "POST",
        "/transaction/initialize",
        json={
            "reference": reference,
            "amount": amount_kobo,
            "currency": "NGN",
            "email": email,
            "callback_url": callback_url,
            "metadata": metadata,
        },
    )
    url = data.get("authorization_url")
    if not url:
        raise PaystackError("Paystack didn't return a checkout page. Try again.")
    return url


def verify(reference: str) -> dict[str, Any]:
    """The transaction as Paystack sees it: {"status": "success"|..., "amount": kobo, "currency"}."""
    return _call("GET", f"/transaction/verify/{reference}")


def signature_ok(raw_body: bytes, signature: str | None) -> bool:
    """A webhook is genuine when x-paystack-signature is the HMAC-SHA512 of the body with our key."""
    if not signature or not available():
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.strip().encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
