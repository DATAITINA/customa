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
    (workspace) can override them through msflib-workspace-config.
    """

    namespace: ClassVar[str] = "CUSTOMA"

    # A customer earns one plate per window: 6 hours in real life.
    PLATE_WINDOW_SECONDS: int = 6 * 60 * 60
    # The plate that earns a jara (a free extra portion).
    PLATES_FOR_JARA: int = 6
    # "Last plates tonight": set by the vendor to sell leftover food before closing.
    LAST_PLATES_LEFT: int = 0
    LAST_PLATES_UNTIL: str | None = None  # ISO time (UTC) when the announcement ends
    # When the last leftover-food alert went out (ISO, UTC): one alert per ALERT_GAP_MINUTES.
    LAST_PLATES_ALERTED_AT: str | None = None
    ALERT_GAP_MINUTES: int = 60
    # Text-message alerts cost the stand money per text: at most this many numbers per stand.
    SMS_MAX_SUBSCRIBERS: int = 300

    # Plate Ajo: customers prepay plates at today's price by transfer to the vendor's own account.
    PLATE_AJO_ENABLED: bool = False
    AJO_BANK_NAME: str | None = None
    AJO_ACCOUNT_NUMBER: str | None = None
    AJO_ACCOUNT_NAME: str | None = None
    # Lunch Crew: friends share one card; each crew jara goes to the next member in turn.
    LUNCH_CREW_ENABLED: bool = False
    LUNCH_CREW_MAX_MEMBERS: int = 6

    # Chat with the stand character: a short, warm chat with each counted plate. After this many
    # customer messages the character closes with a cliffhanger; the chat opens again on the
    # next plate and picks up from there.
    CHAT_MESSAGES_PER_PLATE: int = 8
    # Surprise jara: now and then a plate that is not the jara plate gets a free extra too.
    # Off until the vendor turns it on; about one plate in SURPRISE_JARA_ONE_IN.
    SURPRISE_JARA_ENABLED: bool = False
    SURPRISE_JARA_ONE_IN: int = 15
    # The QR code's scan code changes when the vendor makes a new QR code (old prints stop counting).
    QR_VERSION: int = 1
    # Today's special, set by the vendor. It shows only on the day it was set (Nigeria time).
    TODAYS_SPECIAL: str | None = None
    TODAYS_SPECIAL_DATE: str | None = None  # ISO date, e.g. "2026-10-13"


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


    # Web push for leftover-food alerts (generate with scripts/generate_vapid_keys.py and set
    # them in the backend's environment). Without them, alerts are simply not offered.
    VAPID_PUBLIC_KEY: str | None = None
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_SUBJECT: str = "mailto:alerts@customa.app"

    # Text-message (SMS) leftover-food alerts through Termii: they reach every phone, iPhone and
    # Android, with no app. Without an API key and an approved sender ID, texts are not offered.
    TERMII_API_KEY: str | None = None
    TERMII_SENDER_ID: str | None = None  # approved on the Termii dashboard, e.g. "Customa"
    TERMII_BASE_URL: str = "https://api.ng.termii.com"  # your account's base URL (Termii dashboard)
    TERMII_CHANNEL: str = "dnd"  # "dnd" reaches numbers on Do-Not-Disturb; "generic" does not
    # The customer website, for the link in a text.
    PUBLIC_WEB_URL: str = "https://customa-web.vercel.app"

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
