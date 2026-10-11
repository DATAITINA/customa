"""Service layer for Customa's tables, built on MSFLib's ModelAction.

ModelAction gives us create/read/update/delete, and every write it makes emits
lifecycle events on the app's event bus (for example visit-create-pre-commit).
"""

import secrets
from datetime import UTC, datetime, timedelta

from msflib.actions import ModelAction
from sqlmodel import Session, select

from ..models import (
    Character,
    CharacterCreate,
    CharacterUpdate,
    CrewPlate,
    Customer,
    CustomerCreate,
    CustomerUpdate,
    JaraReward,
    JaraRewardCreate,
    JaraRewardUpdate,
    Rating,
    RatingCreate,
    RatingUpdate,
    Visit,
    VisitCreate,
    VisitUpdate,
)


class PlateTooSoon(Exception):
    """Raised when a customer scans again before their plate window has passed."""

    def __init__(self, seconds_left: int) -> None:
        super().__init__(f"Next plate can be counted in {seconds_left} seconds")
        self.seconds_left = seconds_left


class CharacterAction(ModelAction[Character, CharacterCreate, CharacterUpdate]):
    def get_for_stand(self, session: Session, *, workspace_id: int) -> Character | None:
        return self.get_by_all(session, workspace_id=workspace_id)


class CustomerAction(ModelAction[Customer, CustomerCreate, CustomerUpdate]):
    def get_by_key(self, session: Session, *, workspace_id: int, key: str) -> Customer | None:
        return self.get_by_all(session, workspace_id=workspace_id, key=key)

    def create_for_stand(
        self, session: Session, *, workspace_id: int, data: CustomerCreate
    ) -> Customer:
        # The key is made here, never sent by the client.
        return self.create(
            session,
            data=data,
            update={"workspace_id": workspace_id, "key": secrets.token_urlsafe(16)},
        )


class VisitAction(ModelAction[Visit, VisitCreate, VisitUpdate]):
    def last_for_customer(self, session: Session, *, customer_id: int) -> Visit | None:
        """The customer's last counted plate of any kind (own card or crew card)."""
        visits = self.get_multi_by_expressions(
            session,
            Visit.customer_id == customer_id,
            order_by=Visit.id.desc(),
            limit=1,
        )
        return visits[0] if visits else None

    def last_own_card_visit(self, session: Session, *, customer_id: int) -> Visit | None:
        """The customer's last plate on their OWN card: crew plates (Lunch Crew) are skipped.

        So joining a crew pauses the own card and leaving it resumes where it stopped.
        """
        return session.exec(
            select(Visit)
            .join(CrewPlate, CrewPlate.visit_id == Visit.id, isouter=True)
            .where(Visit.customer_id == customer_id, CrewPlate.id.is_(None))
            .order_by(Visit.id.desc())
            .limit(1)
        ).first()

    def lock_and_check_window(
        self, session: Session, *, customer_id: int, window_seconds: int
    ) -> None:
        """Lock the customer's row, then raise PlateTooSoon if their last plate is too recent.

        This is the anti-cheat rule: one plate per window (6 hours, or 30 seconds on the demo
        stand), per customer, whatever card the plate goes on.
        """
        # Lock this customer's row until the visit is saved, so two scans arriving at
        # the same moment (double tap, network retry, two tabs) cannot both pass the
        # check below and count two plates. Postgres honours this; SQLite ignores it.
        session.exec(select(Customer).where(Customer.id == customer_id).with_for_update()).one()
        last = self.last_for_customer(session, customer_id=customer_id)
        if last is not None:
            next_allowed = last.created_at + timedelta(seconds=window_seconds)
            now = datetime.now(UTC).replace(tzinfo=None)
            if now < next_allowed:
                raise PlateTooSoon(seconds_left=int((next_allowed - now).total_seconds()) + 1)

    def count_plate(
        self,
        session: Session,
        *,
        workspace_id: int,
        customer_id: int,
        window_seconds: int,
        plates_for_jara: int,
    ) -> Visit:
        """Count one plate on the customer's own card, unless their last plate was too recent.

        Plates go 1..plates_for_jara, then restart. The jara on the last plate is issued by
        the visit-create-pre-commit listener (app/eventbus), in the same transaction.
        """
        self.lock_and_check_window(session, customer_id=customer_id, window_seconds=window_seconds)
        last = self.last_own_card_visit(session, customer_id=customer_id)
        if last is None or last.plate_number >= plates_for_jara:
            plate_number = 1
        else:
            plate_number = last.plate_number + 1

        return self.create(
            session,
            data=VisitCreate(),
            update={
                "workspace_id": workspace_id,
                "customer_id": customer_id,
                "plate_number": plate_number,
            },
        )


class RatingAction(ModelAction[Rating, RatingCreate, RatingUpdate]):
    pass


class JaraRewardAction(ModelAction[JaraReward, JaraRewardCreate, JaraRewardUpdate]):
    def issue(
        self, session: Session, *, visit: Visit, customer_id: int | None = None
    ) -> JaraReward:
        """Issue the jara earned on `visit`: to the visit's customer, or to `customer_id`
        (a Lunch Crew jara goes to the member whose turn it is, not always the scanner)."""
        # commit=False: we are inside the visit's own transaction (see app/eventbus).
        return self.create(
            session,
            data=JaraRewardCreate(),
            update={
                "workspace_id": visit.workspace_id,
                "customer_id": customer_id if customer_id is not None else visit.customer_id,
                "visit_id": visit.id,
                "code": "JARA-" + secrets.token_hex(3).upper(),
            },
            commit=False,
        )

    def open_for_customer(
        self, session: Session, *, workspace_id: int, customer_id: int
    ) -> list[JaraReward]:
        """This customer's unredeemed jara codes at this stand, oldest first."""
        return self.get_multi_by_expressions(
            session,
            JaraReward.workspace_id == workspace_id,
            JaraReward.customer_id == customer_id,
            JaraReward.redeemed == False,
            order_by=JaraReward.id,
        )


character_action = CharacterAction()
customer_action = CustomerAction()
visit_action = VisitAction()
rating_action = RatingAction()
jara_action = JaraRewardAction()
