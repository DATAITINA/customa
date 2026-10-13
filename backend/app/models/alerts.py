"""Leftover-food alerts: a customer's phone subscribed to a stand's push notifications.

One row per phone (push endpoint) per stand. Migration: scripts/migrations/2026-10-13_push_alerts.sql.
"""

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
