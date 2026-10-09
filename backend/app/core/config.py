from typing import ClassVar

from msflib.account.config import AccountSettings
from msflib.ai_core.config import AICoreSettings
from msflib.auth.config import AuthSettings
from msflib.core.config import CoreSettings, ModuleSettingsBase, SettingsBase
from msflib.tenancy import TenancySettings
from msflib.workspace_config.config import WorkspaceConfigSettings
from msflib.workspaces.config import WorkspaceSettings


class CustomaSettings(ModuleSettingsBase):
    """Customa's own settings namespace.

    These are tiered: the defaults below apply to every stand, and a stand
    (workspace) can override them through msflib-workspace-config. The demo
    stand overrides PLATE_WINDOW_SECONDS to 30 so a judge can scan twice on stage.
    """

    namespace: ClassVar[str] = "CUSTOMA"

    # A customer earns one plate per window: 6 hours in real life.
    PLATE_WINDOW_SECONDS: int = 6 * 60 * 60
    # The plate that earns a jara (a free extra portion).
    PLATES_FOR_JARA: int = 6


class AppSettings(
    CustomaSettings,
    AICoreSettings,
    WorkspaceConfigSettings,
    WorkspaceSettings,
    TenancySettings,
    AccountSettings,
    AuthSettings,
    CoreSettings,
    SettingsBase,
):
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # Each vendor gets their own stand workspace, created in app/services/stands.py,
    # so new accounts must not be dropped into a shared default workspace.
    AUTO_CREATE_DEFAULT_WORKSPACE: bool = False

    # Login for the seeded demo stand (set real values in .env).
    DEMO_VENDOR_EMAIL: str = "iyabisi@example.com"
    DEMO_VENDOR_PASSWORD: str = "change-me-demo"

    REDIS_HOST: str | None = None
    REDIS_PORT: str | None = None
    REDIS_PASSWORD: str | None = None

    INVALID_JWT_EXPIRE: int | None = 3600
    EMAIL_TEMPLATES_DIR: str = "./app/email-templates/build"
    PASSWORD_RESET_PATH: str = "/password-reset"

    # File storage
    STORAGE_METHOD: str | None = "file"
    STORAGE_PATH: str | None = "./uploads"

    # Server-Sent Event Stream settings.
    STREAM_RETRY_TIMEOUT: int = 15000  # millisecond
    STREAM_DELAY: int = 1  # second


settings = AppSettings()
