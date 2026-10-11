from fastapi import APIRouter
from msflib.account.router import account_router, profile_router
from msflib.auth.router import router as auth_router

from app import models
from app.api import deps
from app.api.api_v1.endpoints import (
    admin,
    lunch_crew,
    plate_ajo,
    pot_alert,
    public,
    session,
    stands,
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
# The three return-visit features: each has a customer router and a vendor router.
for feature in (plate_ajo, pot_alert, lunch_crew):
    api_router.include_router(feature.public_router)
    api_router.include_router(feature.vendor_router)
