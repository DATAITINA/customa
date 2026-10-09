import logging

from msflib.api.deps import get_keystore_factory, get_session_factory
from msflib.auth.deps import get_account_dependencies, get_user_dependencies
from msflib.auth.resolvers import PathParameterResolver

from ..core.config import settings
from ..db.session import engine
from ..models import Account, AccountStatus, User, Workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Session
get_session = get_session_factory(engine)

# Redis Keystore (falls back to MapStore if Redis server is not found).
get_keystore = get_keystore_factory(
    redis_host=settings.REDIS_HOST,
    redis_password=settings.REDIS_PASSWORD,
    redis_port=int(settings.REDIS_PORT) if settings.REDIS_PORT else 6379,
)

account_dependencies = get_account_dependencies(
    AccountModel=Account,
    oauth_token_url=f"{settings.API_V1_STR}/login",
    secret_key=settings.SECRET_KEY,
    active_statuses=[AccountStatus.active, AccountStatus.online],
    session_dep=get_session,
    keystore_dep=get_keystore,
)

get_current_account = account_dependencies.get_current_account
get_current_account_or_none = account_dependencies.get_current_account_or_none
get_current_active_account = account_dependencies.get_current_active_account
get_current_active_superuser = account_dependencies.get_current_active_superuser
RoleCheck = account_dependencies.RoleCheck

# A stand is a workspace. Routes carry its slug in the path ({workspace_slug}),
# and these dependencies find the stand and check the caller is a member of it.
workspace_dependencies = get_user_dependencies(
    UserModel=User,
    WorkspaceModel=Workspace,
    session_dep=get_session,
    account_dependencies=account_dependencies,
    workspace_resolver=PathParameterResolver(),
)

get_current_workspace = workspace_dependencies.get_current_workspace
# Public lookup by slug, no login: used only for the customer page.
get_stand_public = workspace_dependencies.get_current_workspace_anonymous
get_current_active_member = workspace_dependencies.get_current_active_user
