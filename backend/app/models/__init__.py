from msflib.account.models import (
    AccountCreate,
    AccountRead,
    AccountReadPublic,
    AccountReadPublicProfile,
    AccountRole,
    AccountStatus,
    AccountUpdate,
    ProfileCreate,
    ProfileRead,
    ProfileSmall,
    ProfileUpdate,
    UserProfile,
)
from msflib.account.models.account import Account, Profile
from msflib.tenancy.models import TenantCreate, TenantUpdate
from msflib.tenancy.models.tenant import Tenant
from msflib.workspaces.models import (
    UserCreate,
    UserRead,
    UserType,
    UserUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from msflib.workspaces.models.user import User
from msflib.workspaces.models.workspace import Workspace

# Registers the scopedconfigentry table that stores per-stand setting overrides.
from msflib.workspace_config.models import ConfigScopeType, ScopedConfigEntry

# Registers msflib-conversation's tables (saved chats with the stand character).
import msflib.conversation.models  # noqa: E402,F401

from .customa import (
    Character,
    CharacterBody,
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
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
from .alerts import PushSubscription, SmsSubscription  # noqa: E402
from .character_chat import ChatMemory  # noqa: E402
from .lunch_crew import Crew, CrewMember, CrewPlate  # noqa: E402
from .plate_ajo import PlateBundle, PlateUse  # noqa: E402
from .prize_wheel import JaraPrize, WheelItem  # noqa: E402
from .regulars import Arrival, CustomerUsual, VendorPushSubscription  # noqa: E402
from .visit_plans import VisitPlan  # noqa: E402
from .stand_photo import StandPhoto  # noqa: E402
from .payments import Payment, PaymentCreate, PaymentUpdate  # noqa: E402
