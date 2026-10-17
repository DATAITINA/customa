from typing import ClassVar

from msflib.account.config import AccountSettings
from msflib.ai_core.config import AICoreSettings
from msflib.auth.config import AuthSettings
from msflib.core.config import CoreSettings, ModuleSettingsBase, SettingsBase
from msflib.drivelink.config import DrivelinkSettings
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
    # Head-start card: every new card shows this many gift stamps first ("Welcome gift: 2 stamps
    # on us"), so it reads (real plates + 2) / (6 + 2). Display only: the jara still comes after
    # PLATES_FOR_JARA real plates, and the 6-hour rule is unchanged. 0 turns it off.
    HEAD_START_STAMPS: int = 2
    # "Who's here now" on the vendor dashboard: customers whose plate was counted in the last
    # ARRIVAL_WINDOW_MINUTES, so staff can greet regulars by name.
    ARRIVAL_WINDOW_MINUTES: int = 90
    # Plan the next visit: reminders go by web push to customers who turned alerts on. Texts cost
    # money, so SMS reminders (only to customers who already agreed to texts) are off by default.
    PLAN_SMS_REMINDERS: bool = False
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
    # Pay for a plate (Paystack test mode, or cash the vendor confirms): a paid plate counts as a
    # stamp. Off until the vendor turns it on; prices come from the stand's menu.
    PAYMENTS_ENABLED: bool = False
    # Save your card: customers may link their card to their phone number + a 4-digit PIN, and
    # get it back in any browser (another browser, in-app browser, Home Screen app). On by default.
    CARD_RECOVERY_ENABLED: bool = True
    # The QR code's scan code changes when the vendor makes a new QR code (old prints stop counting).
    QR_VERSION: int = 1
    # Today's special, set by the vendor. It shows only on the day it was set (Nigeria time).
    TODAYS_SPECIAL: str | None = None
    TODAYS_SPECIAL_DATE: str | None = None  # ISO date, e.g. "2026-10-13"
    # Prize Wheel: the jara is a spin on the vendor's wheel of food prizes (up to 6). Off until
    # the vendor publishes a wheel with at least 2 prizes. A won prize can be collected for
    # WHEEL_PRIZE_VALID_DAYS days.
    PRIZE_WHEEL_ENABLED: bool = False
    WHEEL_PRIZE_VALID_DAYS: int = 14


class AppSettings(
    CustomaSettings,
    AICoreSettings,
    DrivelinkSettings,
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

    # The scheduler's secret: GET /cron/plan-reminders needs "Authorization: Bearer <CRON_SECRET>".
    # Without it the endpoint refuses every call.
    CRON_SECRET: str | None = None

    # Text-message (SMS) leftover-food alerts through Termii: they reach every phone, iPhone and
    # Android, with no app. Without an API key and an approved sender ID, texts are not offered.
    TERMII_API_KEY: str | None = None
    TERMII_SENDER_ID: str | None = None  # approved on the Termii dashboard, e.g. "Customa"
    TERMII_BASE_URL: str = "https://api.ng.termii.com"  # your account's base URL (Termii dashboard)
    TERMII_CHANNEL: str = "dnd"  # "dnd" reaches numbers on Do-Not-Disturb; "generic" does not
    # The customer website, for the link in a text.
    # Paystack, TEST MODE ONLY: a secret key that starts with sk_test_. A live key (sk_live_) is
    # refused, so no real money can move. Never commit keys: set them on Vercel (docs/payments.md).
    PAYSTACK_SECRET_KEY: str | None = None
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    # Paystack needs an email per payment; customers give none, so each payment gets an address
    # on this domain (nothing is sent to it).
    PAYSTACK_EMAIL_DOMAIN: str = "customers.customa.app"
    # Stand photos as files in the vendor's MSFLib drivelink drive. Needs cloud file storage,
    # because Vercel can't keep files: STORAGE_METHOD=cloudinary with CLOUDINARY_CLOUD_NAME,
    # CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET (or s3/gcs/azure). Off: photos stay in the
    # database, as before.
    STAND_PHOTOS_IN_DRIVELINK: bool = False
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
