"""Lunch Crew tables: a shared card at one stand, its members in join order, and its plates."""

from msflib.models import ModelBase
from sqlalchemy import UniqueConstraint
from sqlmodel import Field


class Crew(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str
    code: str = Field(unique=True, index=True)  # invite code in the share link
    plate_count: int = 0  # crew plates counted so far (plate number = count % jara size + 1)
    # Index into the members ordered by position: whose turn the next crew jara is.
    # Kept in range 0..len(members)-1 (it moves when someone joins after or leaves before).
    next_turn: int = 0


class CrewMember(ModelBase, table=True):
    # One crew per customer per stand.
    __table_args__ = (UniqueConstraint("workspace_id", "customer_id"),)

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    crew_id: int = Field(foreign_key="crew.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    position: int  # join order (1 = creator); gaps are fine after someone leaves


class CrewPlate(ModelBase, table=True):
    """Marks a visit as a crew plate; the jara recipient is set on the crew's jara plate.

    The row stays when its crew is deleted (crew_id becomes NULL), so the visit is still known
    to be a crew plate and never counts on the scanner's own card.
    """

    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    crew_id: int | None = Field(default=None, foreign_key="crew.id", index=True)
    visit_id: int = Field(foreign_key="visit.id", unique=True)
    recipient_customer_id: int | None = Field(default=None, foreign_key="customer.id")
