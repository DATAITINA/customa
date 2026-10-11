"""Counting a plate: the one path used by a QR scan and by a prepaid Plate Ajo plate.

Lunch Crew hooks in here, so every counted plate follows the same rules (6-hour window per
customer, crew card when the customer is in a crew).
"""

from sqlmodel import Session

from ..actions import visit_action
from ..core.config import CustomaSettings
from ..models import Customer, Visit, Workspace


def count_visit(
    session: Session, *, workspace: Workspace, customer: Customer, stand_settings: CustomaSettings
) -> Visit:
    """Count one plate for this customer, or raise PlateTooSoon (see VisitAction.count_plate)."""
    return visit_action.count_plate(
        session,
        workspace_id=workspace.id,
        customer_id=customer.id,
        window_seconds=stand_settings.PLATE_WINDOW_SECONDS,
        plates_for_jara=stand_settings.PLATES_FOR_JARA,
    )
