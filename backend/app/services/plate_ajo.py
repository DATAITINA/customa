"""Plate Ajo: prepaid plates at today's price."""

from sqlmodel import Session

from ..models import Customer, Workspace


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's plate_ajo data at this stand (called by "Delete my data")."""
