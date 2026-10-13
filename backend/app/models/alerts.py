"""Leftover-food alerts: a customer's phone subscribed to a stand's push notifications, and a
customer's phone number for text-message alerts.

PushSubscription: one row per phone (push endpoint) per stand (migration 2026-10-13_push_alerts.sql).
SmsSubscription: one number per customer per stand (migration 2026-10-14_sms_alerts.sql).
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlalchemy import UniqueConstraint
from sqlmodel import Field


class PushSubscription(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "endpoint"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    endpoint: str  # the browser's push service URL (only known push services are accepted)
    p256dh: str  # the phone's public key, to encrypt the message
    auth: str  # the phone's auth secret


class SmsSubscription(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "customer_id"), UniqueConstraint("workspace_id", "phone"))

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    phone: str  # international digits, e.g. "2348031234567"; never shown to the vendor
    agreed_at: datetime  # when the customer agreed to get texts (the terms below)
    terms_version: str  # which wording they agreed to (services/sms_alerts.py TERMS_VERSION)
