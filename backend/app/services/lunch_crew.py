"""Lunch Crew: a shared card with ajo rotation for jara."""

from sqlmodel import Session

from ..models import Customer, Workspace


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's lunch_crew data at this stand (called by "Delete my data")."""
