"""Customa's own tables, built on MSFLib core's ModelBase (id, created_at, updated_at).

A stand is an MSFLib workspace, so every row here carries workspace_id and is
always read and written scoped to one stand.
"""

from typing import Any

from msflib.models import BaseEnum, ModelBase, SchemaBase
from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field


class CharacterBody(BaseEnum):
    pepper = "pepper"
    cup = "cup"
    pot = "pot"
    blob = "blob"


# --- Character: the stand's friendly face (one per stand) -------------------


class CharacterBase(SchemaBase):
    name: str
    body: CharacterBody = CharacterBody.pepper
    color: str = "pepper"  # a colour preset from the character kit
    accessory: str = "headwrap"
    greeting: str = "Welcome! Sit down, food is ready."
    personality: str = "Warm, cheerful, a little playful. Speaks simple English with light Pidgin."
    # [{"item": "Yam and fish", "price": 1500}, ...]
    menu: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class Character(CharacterBase, ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", unique=True, index=True)


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(SchemaBase):
    name: str | None = None
    body: CharacterBody | None = None
    color: str | None = None
    accessory: str | None = None
    greeting: str | None = None
    personality: str | None = None
    menu: list[dict[str, Any]] | None = None


class CharacterRead(CharacterBase):
    id: int


# --- Customer: someone who scanned a stand's QR code ------------------------


class Customer(ModelBase, table=True):
    __table_args__ = (UniqueConstraint("workspace_id", "key"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    # Random id the customer's phone keeps, so we recognise them next time.
    key: str = Field(index=True)
    first_name: str | None = None
    consent: bool = False
    # How the customer first arrived ("qr" for a QR scan). Set once at sign-up, never updated.
    source: str | None = None


class CustomerCreate(SchemaBase):
    first_name: str | None = None
    consent: bool = False
    source: str | None = None


class CustomerUpdate(SchemaBase):
    first_name: str | None = None
    consent: bool | None = None


# --- Visit: one counted plate ------------------------------------------------


class Visit(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    plate_number: int  # 1..PLATES_FOR_JARA, then starts again at 1


class VisitCreate(SchemaBase):
    pass


class VisitUpdate(SchemaBase):
    pass


# --- Rating: how the plate tasted --------------------------------------------


class Rating(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    visit_id: int = Field(foreign_key="visit.id", unique=True)
    stars: int = Field(ge=1, le=5)


class RatingCreate(SchemaBase):
    stars: int = Field(ge=1, le=5)


class RatingUpdate(SchemaBase):
    stars: int | None = Field(default=None, ge=1, le=5)


# --- JaraReward: the free extra earned on the 6th plate ----------------------


class JaraReward(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    visit_id: int = Field(foreign_key="visit.id", unique=True)
    code: str
    redeemed: bool = False


class JaraRewardCreate(SchemaBase):
    pass


class JaraRewardUpdate(SchemaBase):
    redeemed: bool | None = None
