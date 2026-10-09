"""Saved chats with the stand character, stored with msflib-conversation.

Each customer gets one private conversation per stand. The customer posts as a
"user" member and the character posts as an "agent" member, so the vendor can
read what customers ask. Logging never breaks the chat: failures are logged.
"""

import logging
from typing import Any

from msflib.conversation.actions import ConversationAction, MemberAction, MessageAction
from msflib.conversation.contracts import ConversationScope, Participant
from msflib.conversation.enums import MemberKind, SenderKind
from msflib.conversation.models import Conversation, ConversationCreate, Message, MessageCreate
from msflib.conversation.services import AccessService, ChannelService, MembershipService, MessagingService
from sqlmodel import Session, select

from ..models import Customer, Workspace

logger = logging.getLogger("customa.chat")
AGENT_ID = "stand-character"


def _slug(customer: Customer) -> str:
    return f"customer-{customer.id}"


def _person(workspace: Workspace, customer: Customer) -> Participant:
    return Participant(kind=MemberKind.user, id=f"customer-{customer.id}", tenant_id=workspace.tenant_id)


def _conversation_for(session: Session, workspace: Workspace, customer: Customer):
    """Find or create this customer's conversation, and their membership in it."""
    person = _person(workspace, customer)
    existing = ConversationAction().get_by_slug(
        session, tenant_id=workspace.tenant_id, workspace_id=workspace.id, slug=_slug(customer)
    )
    if existing is None:
        return ChannelService().create_channel(
            session,
            scope=ConversationScope(tenant_id=workspace.tenant_id, workspace_id=workspace.id),
            data=ConversationCreate(
                name=f"Chat with {customer.first_name or 'a guest'}",
                slug=_slug(customer),
                visibility="private",
            ),
            created_by=person,
        )
    # AccessService checks the conversation is in this stand and the customer may read it.
    return AccessService().resolve_conversation(
        session,
        scope=ConversationScope(
            tenant_id=workspace.tenant_id, workspace_id=workspace.id, conversation_id=existing.public_id
        ),
        participant=person,
    )


def record_turn(session: Session, *, workspace: Workspace, customer: Customer, question: str, answer: str) -> None:
    try:
        conversation, member = _conversation_for(session, workspace, customer)
        agent_member = MembershipService().add_agent(session, conversation=conversation, agent_id=AGENT_ID)
        messaging = MessagingService()
        messaging.post_message(
            session, conversation=conversation, sender=_person(workspace, customer),
            actor_membership=member, data=MessageCreate(content=question),
        )
        messaging.post_message(
            session, conversation=conversation,
            sender=Participant(kind=MemberKind.agent, id=AGENT_ID, tenant_id=workspace.tenant_id),
            actor_membership=agent_member, data=MessageCreate(content=answer),
        )
    except Exception:
        session.rollback()
        logger.exception("could not save chat turn")


def recent_questions(session: Session, *, workspace: Workspace, limit: int = 10) -> list[dict[str, Any]]:
    """The latest questions customers asked at this stand, for the dashboard."""
    rows = session.exec(
        select(Message, Conversation)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.tenant_id == workspace.tenant_id,
            Message.sender_kind == SenderKind.user,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.id.desc())
        .limit(limit)
    ).all()
    return [
        {"id": m.id, "who": (c.name or "").replace("Chat with ", ""), "question": m.content, "at": m.created_at}
        for m, c in rows
    ]


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Delete-my-data: remove this customer's conversation, messages and memberships."""
    conversation = ConversationAction().get_by_slug(
        session, tenant_id=workspace.tenant_id, workspace_id=workspace.id, slug=_slug(customer)
    )
    if conversation is None:
        return
    MessageAction().delete_multi_by_expressions(session, Message.conversation_id == conversation.id, commit=False)
    member_model = MemberAction()._model()
    MemberAction().delete_multi_by_expressions(session, member_model.conversation_id == conversation.id, commit=False)
    ConversationAction().delete(session, conversation.id)
