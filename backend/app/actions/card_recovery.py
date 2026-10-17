"""Card recovery as MSFLib ModelActions: every read and write of the recovery tables."""

from datetime import datetime

from msflib.actions import ModelAction
from sqlmodel import Session, func, select

from ..models import (
    CustomerDeviceKey,
    CustomerDeviceKeyCreate,
    CustomerDeviceKeyUpdate,
    CustomerPhone,
    CustomerPhoneCreate,
    CustomerPhoneUpdate,
    RecoveryAttempt,
    RecoveryAttemptCreate,
    RecoveryAttemptUpdate,
    RecoveryCode,
    RecoveryCodeCreate,
    RecoveryCodeUpdate,
)


class CustomerPhoneAction(ModelAction[CustomerPhone, CustomerPhoneCreate, CustomerPhoneUpdate]):
    def by_hash(self, session: Session, *, workspace_id: int, phone_hash: str) -> CustomerPhone | None:
        return self.get_by_all(session, workspace_id=workspace_id, phone_hash=phone_hash)

    def for_customer(self, session: Session, *, customer_id: int) -> CustomerPhone | None:
        return self.get_by_all(session, customer_id=customer_id)

    def linked_ids(self, session: Session, *, customer_ids: set[int]) -> set[int]:
        if not customer_ids:
            return set()
        return set(session.exec(select(CustomerPhone.customer_id).where(CustomerPhone.customer_id.in_(customer_ids))).all())


class CustomerDeviceKeyAction(ModelAction[CustomerDeviceKey, CustomerDeviceKeyCreate, CustomerDeviceKeyUpdate]):
    def previous_cards(self, session: Session, *, customer_id: int) -> list[int]:
        """Cards that browsers had before they recovered this customer's card."""
        return [
            d.came_from_customer_id
            for d in self.get_multi_by_expressions(session, CustomerDeviceKey.customer_id == customer_id, limit=None)
            if d.came_from_customer_id
        ]


class RecoveryAttemptAction(ModelAction[RecoveryAttempt, RecoveryAttemptCreate, RecoveryAttemptUpdate]):
    def count(self, session: Session, *, since: datetime, outcomes: tuple[str, ...], **match) -> int:
        q = select(func.count()).select_from(RecoveryAttempt).where(
            RecoveryAttempt.created_at >= since, RecoveryAttempt.outcome.in_(outcomes)
        )
        for field, value in match.items():
            q = q.where(getattr(RecoveryAttempt, field) == value)
        return session.exec(q).one()


class RecoveryCodeAction(ModelAction[RecoveryCode, RecoveryCodeCreate, RecoveryCodeUpdate]):
    def live(self, session: Session, *, workspace_id: int, phone_hash: str, now: datetime) -> RecoveryCode | None:
        rows = self.get_multi_by_expressions(
            session,
            RecoveryCode.workspace_id == workspace_id,
            RecoveryCode.phone_hash == phone_hash,
            RecoveryCode.used_at.is_(None),
            RecoveryCode.expires_at > now,
            order_by=RecoveryCode.id.desc(),
            limit=1,
        )
        return rows[0] if rows else None


customer_phone_action = CustomerPhoneAction()
device_key_action = CustomerDeviceKeyAction()
recovery_attempt_action = RecoveryAttemptAction()
recovery_code_action = RecoveryCodeAction()
