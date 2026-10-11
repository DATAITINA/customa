"""Pot Alert tables: who wants to hear when a dish is ready, and the vendor's "ready now" calls."""

from msflib.models import ModelBase
from sqlalchemy import UniqueConstraint
from sqlmodel import Field


class PotWatch(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "customer_id", "item"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    item: str
    phone: str  # normalised to 234XXXXXXXXXX, shown only to the stand's vendor


class PotReady(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    item: str
    plates_left: int | None = None
    ended: bool = False
