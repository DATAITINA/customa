"""Plan the next visit ("When you go come back?"): one active plan per customer per stand, with
its reminder and what happened (kept, missed, cancelled). A plan, never a reservation.
Migration: scripts/migrations/2026-10-17_visit_plans.sql (new table only).
"""

from datetime import date, datetime

from msflib.models import ModelBase
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field


class VisitPlan(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    day: date  # the planned day (Nigeria time)
    slot: str  # morning, lunch or evening
    status: str = "active"  # active, kept, missed or cancelled
    # The reminder (about 1 hour before the slot), sent once: sent_at is set before sending.
    reminder_due_at: datetime | None = None  # UTC
    reminder_sent_at: datetime | None = None
    reminder_channel: str | None = None  # push, sms or none (nothing the customer agreed to)
    # The plate that kept the plan, and the plate at which the customer was told how it went.
    kept_visit_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("visit.id", ondelete="SET NULL"), nullable=True)
    )
    noted_visit_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("visit.id", ondelete="SET NULL"), nullable=True)
    )
