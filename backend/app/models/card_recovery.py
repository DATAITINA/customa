"""Customer card recovery: a customer's card follows the customer, not the browser.

CustomerPhone: the number a customer linked to their card at one stand, stored only as a keyed
  hash (for lookup) and a masked form (0803 ••• 4521, for display), with a bcrypt-hashed PIN.
CustomerDeviceKey: an extra key for the same customer, given to another browser after it
  proved ownership. `came_from_customer_id` is the card that browser had before (if any), so a
  plate counted there still holds the 6-hour window.
RecoveryAttempt: every link and recovery attempt (security log, rate limits, lockouts).
RecoveryCode: a 6-digit SMS code (hashed), only when the stand can send texts.
New tables only (migration 2026-10-19_card_recovery.sql).
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CustomerPhone(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "phone_hash"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", unique=True, index=True)
    phone_hash: str = Field(index=True)  # HMAC-SHA256(SECRET_KEY, stand + number): never the number
    phone_masked: str  # "0803 ••• 4521"
    pin_hash: str  # bcrypt, via msflib.core.security


class CustomerPhoneCreate(SQLModel):
    phone_hash: str
    phone_masked: str
    pin_hash: str


class CustomerPhoneUpdate(SQLModel):
    phone_hash: str | None = None
    phone_masked: str | None = None
    pin_hash: str | None = None


class CustomerDeviceKey(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "key"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    key: str = Field(index=True)
    came_from_customer_id: int | None = Field(default=None, foreign_key="customer.id")


class CustomerDeviceKeyCreate(SQLModel):
    key: str
    came_from_customer_id: int | None = None


class CustomerDeviceKeyUpdate(SQLModel):
    came_from_customer_id: int | None = None


class RecoveryAttempt(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    phone_hash: str = Field(index=True)
    ip_hash: str = Field(index=True)
    customer_id: int | None = Field(default=None, foreign_key="customer.id")  # set on success
    kind: str  # link, pin, sms_send, sms_code
    outcome: str  # ok, wrong, locked, limited, taken, sent, skipped


class RecoveryAttemptCreate(SQLModel):
    phone_hash: str
    ip_hash: str
    kind: str
    outcome: str
    customer_id: int | None = None


class RecoveryAttemptUpdate(SQLModel):
    outcome: str | None = None


class RecoveryCode(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    phone_hash: str = Field(index=True)
    code_hash: str  # bcrypt
    expires_at: datetime
    used_at: datetime | None = None


class RecoveryCodeCreate(SQLModel):
    phone_hash: str
    code_hash: str
    expires_at: datetime


class RecoveryCodeUpdate(SQLModel):
    used_at: datetime | None = None
