"""Pot Alert: tell me when my dish is ready."""

from sqlmodel import Session

from ..models import Customer, Workspace


def forget_customer(session: Session, *, workspace: Workspace, customer: Customer) -> None:
    """Remove this customer's pot_alert data at this stand (called by "Delete my data")."""
