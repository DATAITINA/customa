"""Regular-arrived alert ("Ime don land!"): who is at the stand now, for staff to greet by name.

Arrival: one row per counted plate (the customer's nth plate at the stand, when they last came,
and when staff tapped "Greeted"), so greeting can be measured. CustomerUsual: the menu item a
customer chose to share as "my usual" (off until they turn it on; never taken from the chat).
VendorPushSubscription: a vendor's phone that asked to be pinged when regulars arrive.
Migration: scripts/migrations/2026-10-16_regulars.sql (new tables only).
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field


class Arrival(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    # The counted plate; deleting the plate deletes its arrival.
    visit_id: int = Field(
        sa_column=Column(Integer, ForeignKey("visit.id", ondelete="CASCADE"), unique=True, nullable=False)
    )
    visit_number: int  # the customer's nth counted plate at this stand (1 = first time)
    previous_at: datetime | None = None  # their plate before this one
    greeted_at: datetime | None = None  # staff tapped "Greeted"
    pinged_at: datetime | None = None  # the vendor's phones were pinged (once per visit)


class CustomerUsual(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", unique=True)
    item: str  # a menu item the customer picked


class VendorPushSubscription(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "endpoint"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    endpoint: str  # the browser's push service URL (only known push services are accepted)
    p256dh: str
    auth: str
