"""What the stand character keeps about one customer, privately (one row per customer).

The vendor never reads this table: the dashboard only shows food questions. The customer can
see it on the chat page and clear it, and delete-my-data removes it.
Migration: scripts/migrations/2026-10-13_chat_memory.sql.
"""

from msflib.models import ModelBase
from sqlmodel import Field


class ChatMemory(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", unique=True, index=True)

    # This visit's chat: it opens with each counted plate (visit_id) and closes, with a warm
    # cliffhanger, after CHAT_MESSAGES_PER_PLATE messages.
    visit_id: int | None = Field(default=None, foreign_key="visit.id")
    messages_used: int = 0
    closed: bool = False
    opener: str | None = None  # the character's first line for this visit, kept for page reloads

    # Memory the customer can see and clear.
    favourite_item: str | None = None  # a menu item they said they love
    last_item: str | None = None  # the last menu item they talked about
    follow_up: str | None = None  # a question to pick the chat up next visit
