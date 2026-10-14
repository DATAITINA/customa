"""Counting a plate: the one path used by a QR scan and by a prepaid Plate Ajo plate.

Lunch Crew hooks in here, so every counted plate follows the same rules (6-hour window per
customer, crew card when the customer is in a crew). After a plate is counted, the regular-arrived
alert records the arrival (services/regulars.py).
"""

from datetime import UTC, datetime

from sqlmodel import Session

from ..actions import visit_action
from ..core.config import CustomaSettings
from ..models import Customer, Visit, Workspace
from . import lunch_crew, regulars


def count_visit(
    session: Session, *, workspace: Workspace, customer: Customer, stand_settings: CustomaSettings
) -> Visit:
    """Count one plate for this customer, or raise PlateTooSoon (see VisitAction.count_plate).

    The plate goes on the customer's crew card when Lunch Crew is on at this stand and they are
    in a crew (Visit.plate_number is then the crew card's number; a CrewPlate row marks it, and
    a crew jara may go to another member). Otherwise it goes on their own card, exactly as
    before. Either way the visit is committed when this returns.
    """
    visit = lunch_crew.count_crew_plate(
        session, workspace=workspace, customer=customer, stand_settings=stand_settings
    )
    if visit is None:
        visit = visit_action.count_plate(
            session,
            workspace_id=workspace.id,
            customer_id=customer.id,
            window_seconds=stand_settings.PLATE_WINDOW_SECONDS,
            plates_for_jara=stand_settings.PLATES_FOR_JARA,
        )
    after_count(session, workspace=workspace, customer=customer, visit=visit)
    return visit


def after_count(session: Session, *, workspace: Workspace, customer: Customer, visit: Visit) -> None:
    """Every counted plate, after it is committed: "Who's here now" for the staff."""
    now = datetime.now(UTC).replace(tzinfo=None)
    regulars.record_arrival(session, workspace=workspace, customer=customer, visit=visit, now=now)
