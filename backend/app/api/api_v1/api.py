from fastapi import APIRouter
from msflib.account.router import account_router, profile_router
from msflib.auth.router import router as auth_router

from app import models
from app.api import deps
from app.api.api_v1.endpoints import (
    admin,
    alerts,
    assistant,
    card_recovery,
    delights,
    lunch_crew,
    payments,
    plate_ajo,
    prize_wheel,
    public,
    regulars,
    session,
    stands,
    visit_plans,
)
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(
    auth_router(
        get_session=deps.get_session,
        get_keystore=deps.get_keystore,
        get_current_account=deps.get_current_account,
        account_type=models.Account,
        account_read_type=models.AccountRead,
        settings=settings,
        active_statuses=[models.AccountStatus.active, models.AccountStatus.online],
        prefix="",
        tags=["auth"],
    )
)

api_router.include_router(
    account_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        settings=settings,
        account_type=models.Account,
        profile_type=models.Profile,
        account_read_type=models.AccountRead,
        prefix="",
        tags=["accounts"],
    )
)

api_router.include_router(
    profile_router(
        get_session=deps.get_session,
        get_current_account=deps.get_current_account,
        get_current_active_account=deps.get_current_active_account,
        settings=settings,
        profile_type=models.Profile,
        account_type=models.Account,
        profile_read_type=models.ProfileRead,
        prefix="/profiles",
        tags=["profiles"],
    )
)

api_router.include_router(admin.router, prefix="/admin")

# Customa's own routes.
api_router.include_router(session.router)
api_router.include_router(stands.router)
api_router.include_router(public.router)
# The return-visit features: each has a customer router and a vendor router.
for feature in (plate_ajo, lunch_crew):
    api_router.include_router(feature.public_router)
    api_router.include_router(feature.vendor_router)
# The Prize Wheel: the vendor's wheel of food prizes, the customer's spin, the jara code check.
api_router.include_router(prize_wheel.public_router)
api_router.include_router(prize_wheel.vendor_router)
# Regular-arrived alert: "Greeted", the vendor's phone pings, the customer's own "my usual".
api_router.include_router(regulars.vendor_router)
api_router.include_router(regulars.public_router)
# Plan the next visit: the customer's plan and calendar file; the scheduler's reminder run.
api_router.include_router(visit_plans.public_router)
api_router.include_router(visit_plans.cron_router)
# Customer delights (surprise jara, today's special): vendor settings only.
api_router.include_router(delights.vendor_router)
# Leftover-food alerts (web push): customers turn them on; the vendor's last-plates sends them.
api_router.include_router(alerts.public_router)
# Pay for a plate (Paystack test mode, or cash the vendor confirms): a paid plate is a stamp.
api_router.include_router(payments.public_router)
api_router.include_router(payments.vendor_router)
api_router.include_router(payments.webhook_router)
# Save your card / "Already have a card?": a customer's card follows them to any browser.
api_router.include_router(card_recovery.router)
# Ask about your stand: MSFLib ai-api's agent router with Customa's read-only stand tools.
api_router.include_router(assistant.router)
