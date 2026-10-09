import logging
import os

from dotenv import load_dotenv

# Ensure env variables are loaded.
load_dotenv()

from sqlalchemy import inspect  # noqa: E402

from .db.init_db import init_db  # noqa: E402
from .db.session import Session, engine  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def should_reset_db() -> bool:
    reset_requested = os.getenv("INITIAL_DATA_RESET_DB", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    # Explicit reset request
    if reset_requested:
        return True

    # Otherwise inspect database
    inspector = inspect(engine)
    existing_tables = {t.lower() for t in inspector.get_table_names()}

    # Check if any of our application's defined tables already exist.
    # This is robust against pre-existing system or extension tables
    # (e.g., PostGIS spatial_ref_sys).
    from sqlmodel import SQLModel

    from app import models  # noqa: F401

    app_tables = {table.name.lower() for table in SQLModel.metadata.tables.values()}

    if not app_tables:
        logger.warning(
            "No application tables found in SQLModel metadata. "
            "This can happen if models are not imported before calling should_reset_db()."
        )
        return not existing_tables

    # If none of our tables exist, we treat the database as empty/uninitialized.
    return not (app_tables & existing_tables)


def init() -> None:
    with Session(engine):
        init_db(engine, create_tables=should_reset_db())


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
