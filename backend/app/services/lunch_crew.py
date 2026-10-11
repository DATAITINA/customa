"""Lunch Crew: a shared card with ajo rotation for jara.

3 to 6 friends share ONE card at a stand. Every member's counted plate adds to the crew card
(1..PLATES_FOR_JARA), and the crew's jara plate issues a jara to the member whose turn it is
(members in join order, rotating), like an ajo payout. The vendor's cost is unchanged: one jara
per PLATES_FOR_JARA plates.

Rules kept from the individual card:
- the wait between plates (6 hours) is per customer, whatever card the plate goes on;
- a customer who is not in a crew, or whose stand has Lunch Crew off, counts exactly as before.

The crew applies only when LUNCH_CREW_ENABLED is on AND the customer is a member at that stand.
Crew plates are marked by a CrewPlate row; the own card skips them (see
VisitAction.last_own_card_visit), so joining a crew pauses the own card and leaving resumes it.
"""

import secrets
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, func, select

from ..actions import jara_action, visit_action
from ..core.config import CustomaSettings
from ..models import (
    Crew,
    CrewMember,
    CrewPlate,
    Customer,
    JaraReward,
    Visit,
    VisitCreate,
    Workspace,
)

# Customers whose visit being created right now is a crew plate. The individual jara listener
# (app/eventbus) reads this and skips them: the crew jara is issued here, to whoever's turn it is.
CREW_PLATE_MARK = "customa.crew_plate_customers"

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, easy to read aloud
NAME_MIN, NAME_MAX = 2, 30


class CrewError(Exception):
    """A request we refuse, with an HTTP status and a message that can be shown as is."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def display_name(customer: Customer | None) -> str:
    return (customer.first_name if customer else None) or "Guest"


# --- Reads -----------------------------------------------------------------------------------


def membership(session: Session, *, workspace_id: int, customer_id: int) -> CrewMember | None:
    return session.exec(
        select(CrewMember).where(
            CrewMember.workspace_id == workspace_id, CrewMember.customer_id == customer_id
        )
    ).first()


def members_with_customers(session: Session, *, crew_id: int) -> list[tuple[CrewMember, Customer]]:
    """The crew's members in join order, each with their customer row."""
    return list(
        session.exec(
            select(CrewMember, Customer)
            .join(Customer, Customer.id == CrewMember.customer_id)
            .where(CrewMember.crew_id == crew_id)
            .order_by(CrewMember.position, CrewMember.id)
        ).all()
    )


def _members(session: Session, *, crew_id: int) -> list[CrewMember]:
    return list(
        session.exec(
            select(CrewMember)
            .where(CrewMember.crew_id == crew_id)
            .order_by(CrewMember.position, CrewMember.id)
        ).all()
    )


def _lock_crew(session: Session, crew_id: int) -> Crew | None:
    # Lock the crew row until commit, so two members scanning at once cannot get the same
    # plate number or both take the same turn. Postgres honours this; SQLite ignores it.
    return session.exec(
        select(Crew)
        .where(Crew.id == crew_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def crew_by_code(session: Session, *, workspace_id: int, code: str) -> Crew | None:
    return session.exec(
        select(Crew).where(Crew.workspace_id == workspace_id, Crew.code == code.strip().upper())
    ).first()


def card_for_customer(
    session: Session, *, workspace_id: int, customer_id: int, stand_settings: CustomaSettings
) -> tuple[str, int] | None:
    """(crew name, last plate number on the crew card) when this customer's plates go to a
    crew, else None. Like the own card, the number is the last plate counted (0 = none yet)."""
    if not stand_settings.LUNCH_CREW_ENABLED:
        return None
    member = membership(session, workspace_id=workspace_id, customer_id=customer_id)
    if member is None:
        return None
    crew = session.get(Crew, member.crew_id)
    if crew is None:
        return None
    n = stand_settings.PLATES_FOR_JARA
    return crew.name, (0 if crew.plate_count == 0 else (crew.plate_count - 1) % n + 1)


# --- Counting a crew plate -------------------------------------------------------------------


def is_crew_plate_in_progress(session: Session, visit: Visit) -> bool:
    """True while count_crew_plate is creating this visit (read by the jara listener)."""
    if visit.customer_id in session.info.get(CREW_PLATE_MARK, ()):
        return True
    if visit.id is None:
        return False
    return (
        session.exec(select(CrewPlate.id).where(CrewPlate.visit_id == visit.id)).first() is not None
    )


def count_crew_plate(
    session: Session, *, workspace: Workspace, customer: Customer, stand_settings: CustomaSettings
) -> Visit | None:
    """Count this plate on the customer's crew card, or return None when it is not a crew plate
    (Lunch Crew off, or not a member): the caller then counts it on the customer's own card.

    Raises PlateTooSoon (the customer's own 6-hour rule) like the own card. The visit, the
    crew's new count and turn, the CrewPlate link and any crew jara are committed together.
    """
    if not stand_settings.LUNCH_CREW_ENABLED:
        return None
    if membership(session, workspace_id=workspace.id, customer_id=customer.id) is None:
        return None

    visit_action.lock_and_check_window(
        session, customer_id=customer.id, window_seconds=stand_settings.PLATE_WINDOW_SECONDS
    )
    # Re-read the membership after locking the crew: the customer may have just left it.
    member = membership(session, workspace_id=workspace.id, customer_id=customer.id)
    crew = _lock_crew(session, member.crew_id) if member else None
    members = _members(session, crew_id=crew.id) if crew else []
    if crew is None or all(m.customer_id != customer.id for m in members):
        return None

    n = stand_settings.PLATES_FOR_JARA
    plate_number = crew.plate_count % n + 1
    crew.plate_count += 1
    recipient_id: int | None = None
    if plate_number == n:
        turn = crew.next_turn % len(members)
        recipient_id = members[turn].customer_id
        crew.next_turn = (turn + 1) % len(members)
    session.add(crew)

    marks: set[int] = session.info.setdefault(CREW_PLATE_MARK, set())
    marks.add(customer.id)
    try:
        visit = visit_action.create(
            session,
            data=VisitCreate(),
            update={
                "workspace_id": workspace.id,
                "customer_id": customer.id,
                "plate_number": plate_number,
            },
            commit=False,
        )
        if visit.id is None:
            session.flush()
        session.add(
            CrewPlate(
                workspace_id=workspace.id,
                crew_id=crew.id,
                visit_id=visit.id,
                recipient_customer_id=recipient_id,
            )
        )
        if recipient_id is not None:
            jara_action.issue(session, visit=visit, customer_id=recipient_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        marks.discard(customer.id)
    session.refresh(visit)
    return visit


def count_result(
    session: Session, *, visit: Visit, customer_id: int, stand_settings: CustomaSettings
) -> dict[str, Any] | None:
    """The crew part of a count response, or None when this visit was not a crew plate."""
    link = session.exec(select(CrewPlate).where(CrewPlate.visit_id == visit.id)).first()
    if link is None:
        return None
    crew = session.get(Crew, link.crew_id) if link.crew_id else None
    recipient = (
        session.get(Customer, link.recipient_customer_id) if link.recipient_customer_id else None
    )
    return {
        "name": crew.name if crew else "",
        "plate_number": visit.plate_number,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "jara_to": display_name(recipient) if link.recipient_customer_id else None,
        "jara_to_me": link.recipient_customer_id == customer_id,
    }


# --- Create, join, leave ---------------------------------------------------------------------


def _require_enabled(stand_settings: CustomaSettings) -> None:
    if not stand_settings.LUNCH_CREW_ENABLED:
        raise CrewError(403, "Lunch Crew is not on at this stand")


def _new_code(session: Session) -> str:
    for length in (6, 6, 6, 7, 7, 8, 8, 8):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
        if session.exec(select(Crew.id).where(Crew.code == code)).first() is None:
            return code
    raise CrewError(503, "Could not make an invite code, please try again")


def create_crew(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    name: str,
    stand_settings: CustomaSettings,
) -> Crew:
    _require_enabled(stand_settings)
    name = " ".join((name or "").split())
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise CrewError(422, f"Crew name must be {NAME_MIN} to {NAME_MAX} characters")
    if membership(session, workspace_id=workspace.id, customer_id=customer.id) is not None:
        raise CrewError(409, "You are already in a crew at this stand")
    crew = Crew(workspace_id=workspace.id, name=name, code=_new_code(session))
    session.add(crew)
    try:
        session.flush()
        session.add(
            CrewMember(
                workspace_id=workspace.id, crew_id=crew.id, customer_id=customer.id, position=1
            )
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise CrewError(409, "You are already in a crew at this stand")
    session.refresh(crew)
    return crew


def join_crew(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer,
    code: str,
    stand_settings: CustomaSettings,
) -> Crew:
    _require_enabled(stand_settings)
    found = crew_by_code(session, workspace_id=workspace.id, code=code or "")
    if found is None:
        raise CrewError(404, "No crew with that invite at this stand")
    current = membership(session, workspace_id=workspace.id, customer_id=customer.id)
    if current is not None:
        if current.crew_id == found.id:
            raise CrewError(409, "You are already in this crew")
        raise CrewError(409, "You are already in a crew at this stand. Leave it first")
    crew = _lock_crew(session, found.id)
    if crew is None:
        raise CrewError(404, "No crew with that invite at this stand")
    members = _members(session, crew_id=crew.id)
    if len(members) >= stand_settings.LUNCH_CREW_MAX_MEMBERS:
        session.rollback()
        raise CrewError(409, "This crew is full")
    position = max((m.position for m in members), default=0) + 1
    # Joining at the end of the line never moves next_turn: the same person is still next.
    session.add(
        CrewMember(
            workspace_id=workspace.id, crew_id=crew.id, customer_id=customer.id, position=position
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise CrewError(409, "You are already in a crew at this stand")
    session.refresh(crew)
    return crew


def _remove_member(session: Session, member: CrewMember) -> None:
    """Take this member out of their crew (no commit). Keeps the same person next in line when
    possible; an empty crew is deleted, and its plates stay marked as crew plates."""
    crew = _lock_crew(session, member.crew_id)
    members = _members(session, crew_id=member.crew_id)
    index = next((i for i, m in enumerate(members) if m.id == member.id), None)
    session.delete(member)
    session.flush()
    if crew is None:
        return
    remaining = len(members) - (1 if index is not None else 0)
    if remaining <= 0:
        session.exec(update(CrewPlate).where(CrewPlate.crew_id == crew.id).values(crew_id=None))
        session.delete(crew)
        session.flush()
        return
    turn = crew.next_turn % max(1, len(members))
    if index is not None and index < turn:
        turn -= 1  # someone before the next person left: the same person stays next
    # If the next person left, the one after them moves into their slot and is next.
    crew.next_turn = turn % remaining
    session.add(crew)
    session.flush()


def leave_crew(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    member = membership(session, workspace_id=workspace.id, customer_id=customer.id)
    if member is None:
        raise CrewError(404, "You are not in a crew at this stand")
    _remove_member(session, member)
    session.commit()


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's lunch_crew data at this stand (called by "Delete my data").

    Runs before the customer's ratings, jara and visits are deleted, so no foreign key ever
    points at a row that is about to go:
    - a crew jara won by ANOTHER member on one of this customer's plates is moved to one of the
      winner's own plates (the winner keeps their reward); if they have none free, it is removed;
    - CrewPlate links on this customer's plates are deleted;
    - where this customer won a crew jara on someone else's plate, the link forgets them;
    - the customer leaves their crew (an empty crew is deleted).
    Nothing is committed here; the caller's deletes commit it all.
    """
    my_visits = select(Visit.id).where(Visit.customer_id == customer.id)
    others_jara = session.exec(
        select(JaraReward).where(
            JaraReward.visit_id.in_(my_visits), JaraReward.customer_id != customer.id
        )
    ).all()
    for jara in others_jara:
        free_visit = session.exec(
            select(Visit.id)
            .where(
                Visit.customer_id == jara.customer_id,
                Visit.id.not_in(select(JaraReward.visit_id)),
            )
            .order_by(Visit.id.desc())
            .limit(1)
        ).first()
        if free_visit is not None:
            jara.visit_id = free_visit
            session.add(jara)
        else:
            session.delete(jara)
        session.flush()

    session.exec(delete(CrewPlate).where(CrewPlate.visit_id.in_(my_visits)))
    session.exec(
        update(CrewPlate)
        .where(CrewPlate.recipient_customer_id == customer.id)
        .values(recipient_customer_id=None)
    )
    member = membership(session, workspace_id=workspace.id, customer_id=customer.id)
    if member is not None:
        _remove_member(session, member)
    session.flush()


# --- Views -----------------------------------------------------------------------------------


def _crew_summary(
    crew: Crew, rows: list[tuple[CrewMember, Customer]], plates_for_jara: int
) -> dict[str, Any]:
    turn = crew.next_turn % len(rows) if rows else 0
    return {
        "name": crew.name,
        "members": [display_name(c) for _, c in rows],
        "plate_number": crew.plate_count % plates_for_jara,
        "plates_for_jara": plates_for_jara,
        "next_jara_to": display_name(rows[turn][1]) if rows else None,
    }


def crew_view(
    session: Session, *, crew: Crew, customer_id: int | None, stand_settings: CustomaSettings
) -> dict[str, Any]:
    """The crew card as a member sees it. plate_number = plates on the current card (0..N-1);
    my_turn_position = 1 when the next crew jara is mine, 2 when it is after the next one..."""
    rows = members_with_customers(session, crew_id=crew.id)
    turn = crew.next_turn % len(rows) if rows else 0
    me = next((i for i, (_, c) in enumerate(rows) if c.id == customer_id), None)
    return {
        **_crew_summary(crew, rows, stand_settings.PLATES_FOR_JARA),
        "code": crew.code,
        "max_members": stand_settings.LUNCH_CREW_MAX_MEMBERS,
        "members": [
            {"name": display_name(c), "is_me": c.id == customer_id, "is_next": i == turn}
            for i, (_, c) in enumerate(rows)
        ],
        "my_turn_position": ((me - turn) % len(rows)) + 1 if me is not None else None,
    }


def public_state(
    session: Session,
    *,
    workspace: Workspace,
    customer: Customer | None,
    code: str | None,
    stand_settings: CustomaSettings,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "enabled": stand_settings.LUNCH_CREW_ENABLED,
        "max_members": stand_settings.LUNCH_CREW_MAX_MEMBERS,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "crew": None,
        "invite": None,
    }
    if not stand_settings.LUNCH_CREW_ENABLED:
        return out
    my_crew: Crew | None = None
    if customer is not None:
        member = membership(session, workspace_id=workspace.id, customer_id=customer.id)
        my_crew = session.get(Crew, member.crew_id) if member else None
        if my_crew is not None:
            out["crew"] = crew_view(
                session, crew=my_crew, customer_id=customer.id, stand_settings=stand_settings
            )
    if code:
        invited = crew_by_code(session, workspace_id=workspace.id, code=code)
        if invited is not None and (my_crew is None or invited.id != my_crew.id):
            count = session.exec(
                select(func.count(CrewMember.id)).where(CrewMember.crew_id == invited.id)
            ).one()
            out["invite"] = {
                "name": invited.name,
                "code": invited.code,
                "members_count": count,
                "max_members": stand_settings.LUNCH_CREW_MAX_MEMBERS,
                "full": count >= stand_settings.LUNCH_CREW_MAX_MEMBERS,
            }
    return out


def vendor_state(
    session: Session, *, workspace: Workspace, stand_settings: CustomaSettings
) -> dict[str, Any]:
    crews = session.exec(
        select(Crew).where(Crew.workspace_id == workspace.id).order_by(Crew.id.desc())
    ).all()
    rows = session.exec(
        select(CrewMember, Customer)
        .join(Customer, Customer.id == CrewMember.customer_id)
        .where(CrewMember.workspace_id == workspace.id)
        .order_by(CrewMember.position, CrewMember.id)
    ).all()
    by_crew: dict[int, list[tuple[CrewMember, Customer]]] = {}
    for member, customer in rows:
        by_crew.setdefault(member.crew_id, []).append((member, customer))
    return {
        "enabled": stand_settings.LUNCH_CREW_ENABLED,
        "max_members": stand_settings.LUNCH_CREW_MAX_MEMBERS,
        "plates_for_jara": stand_settings.PLATES_FOR_JARA,
        "crews": [
            _crew_summary(crew, by_crew.get(crew.id, []), stand_settings.PLATES_FOR_JARA)
            for crew in crews
        ],
    }
