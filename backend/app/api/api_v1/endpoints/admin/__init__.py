from fastapi import APIRouter
from msflib.account.router import account_admin_router

from app import actions, models
from app.api import deps
from app.core.config import settings

# Admin routes.
router = APIRouter()
router.include_router(
    account_admin_router(
        get_session=deps.get_session,
        role_check=deps.RoleCheck,
        settings=settings,
        account_type=models.Account,
        profile_type=models.Profile,
        account_read_type=models.AccountRead,
        account_action=actions.account_action,
        profile_action=actions.profile_action,
        prefix="",
    ),
    prefix="/accounts",
    tags=["admin", "accounts"],
)
