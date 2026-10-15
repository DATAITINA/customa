"""Prize Wheel: the vendor's food prizes (up to 6) and each customer's spin result.

WheelItem: one food prize on a stand's wheel, with an optional photo (stored small, like
StandPhoto). JaraPrize: what a jara won on the wheel, decided by the server at spin time, with
the jara's redemption code and its life from spin to redemption.
Migration: scripts/migrations/2026-10-15_prize_wheel.sql (new tables only).
"""

from datetime import datetime

from msflib.models import ModelBase
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field


class WheelItem(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    position: int = 0  # order on the wheel
    name: str  # the food, e.g. "Jollof rice"
    description: str | None = None
    prize: str | None = None  # what the customer gets, e.g. "A free extra portion"
    # How often it comes up: 1 rarely, 3 sometimes, 5 often. Its slice of the wheel has this size.
    weight: int = 3
    available: bool = True  # off when the food is finished today: not on the wheel
    photo_type: str | None = None  # image/jpeg, image/png or image/webp
    photo_data: str | None = None  # base64
    photo_version: int = 0  # part of the photo URL, so phones cache each version for good


class JaraPrize(ModelBase, table=True):
    # The jara this spin used: one spin per jara. Deleting the jara deletes its prize.
    jara_id: int = Field(
        sa_column=Column(Integer, ForeignKey("jarareward.id", ondelete="CASCADE"), unique=True, nullable=False)
    )
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    # The item won; the name and prize are copied, so the vendor can change the wheel later.
    item_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("wheelitem.id", ondelete="SET NULL"), nullable=True)
    )
    name: str
    prize: str | None = None
    photo_path: str | None = None
    # The wheel as it was at the spin (JSON list of slices) and where it stopped, so the phone
    # shows the same spin again after a reload.
    wheel: str
    slot: int
    landing: float  # 0..1: where in the slice the pointer stopped
    expires_at: datetime
    redeemed_at: datetime | None = None
