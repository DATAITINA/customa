"""Payments as an MSFLib ModelAction: all reads and writes of Payment rows go through here."""

from msflib.actions import ModelAction
from sqlmodel import Session

from ..models import Payment, PaymentCreate, PaymentUpdate


class PaymentAction(ModelAction[Payment, PaymentCreate, PaymentUpdate]):
    def by_reference(self, session: Session, *, reference: str) -> Payment | None:
        return self.get_by_all(session, reference=reference)

    def for_workspace_since(self, session: Session, *, workspace_id: int, since) -> list[Payment]:
        return self.get_multi_by_expressions(
            session,
            Payment.workspace_id == workspace_id,
            Payment.created_at >= since,
            order_by=Payment.id.desc(),
            limit=500,
        )


payment_action = PaymentAction()
