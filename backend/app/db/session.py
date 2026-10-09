from sqlmodel import create_engine, Session  # noqa
from msflib.core.config import CoreSettings
from app.core.config import settings

core_settings: CoreSettings = settings.scope("CORE")
if core_settings.USE_SQLITE:
    engine = create_engine(
        core_settings.SQLITE_DATABASE_URI,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
else:
    engine = create_engine(
        str(core_settings.SQLALCHEMY_DATABASE_URI),
        pool_pre_ping=True,
        echo=core_settings.DB_DEBUG_MODE,
    )
