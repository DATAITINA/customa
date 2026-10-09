from msflib.account.actions import AccountAction, ProfileAction
from msflib.tenancy import TenantAction
from msflib.workspaces.actions import UserAction, WorkspaceAction

from ..core.config import settings
from ..models import (
    Account,
    AccountCreate,
    AccountUpdate,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    Tenant,
    TenantCreate,
    TenantUpdate,
    User,
    UserCreate,
    UserUpdate,
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
)

tenant_action = TenantAction[Tenant, TenantCreate, TenantUpdate]()

account_action = AccountAction[Account, AccountCreate, AccountUpdate](settings=settings)

profile_action = ProfileAction[Profile, ProfileCreate, ProfileUpdate]()

workspace_action = WorkspaceAction[Workspace, WorkspaceCreate, WorkspaceUpdate](settings=settings)

user_action = UserAction[User, UserCreate, UserUpdate]()

from .customa import (  # noqa: E402
    PlateTooSoon,
    character_action,
    customer_action,
    jara_action,
    rating_action,
    visit_action,
)
