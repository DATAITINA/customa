"""Pay for a plate: one row per payment, by Paystack (test mode) or cash the vendor confirms.

A paid payment counts the plate as a stamp (the usual 6-hour rule still applies: a second plate
inside the window is paid but not stamped, and `visit_id` stays empty). New table only
(migration 2026-10-18_payments.sql).
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlmodel import Field, SQLModel


class Payment(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    # Empty after the customer deletes their data: the vendor's takings stay, the person goes.
    customer_id: int | None = Field(default=None, foreign_key="customer.id", index=True)
    reference: str = Field(unique=True, index=True)  # ours, also the Paystack reference
    method: str  # "paystack" or "cash"
    status: str = "pending"  # pending, paid, failed, cancelled
    item: str  # the menu item paid for
    amount_naira: int  # from the stand's menu, never from the customer's screen
    match_code: str  # 3 letters the customer shows the vendor (cash)
    visit_id: int | None = Field(default=None, foreign_key="visit.id")  # the stamp it counted
    paid_at: datetime | None = None
    confirmed_by: int | None = None  # account id of the staff member who confirmed cash


class PaymentCreate(SQLModel):
    reference: str
    method: str
    item: str
    amount_naira: int
    match_code: str


class PaymentUpdate(SQLModel):
    status: str | None = None
    visit_id: int | None = None
    paid_at: datetime | None = None
    confirmed_by: int | None = None
