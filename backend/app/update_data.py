import logging

from sqlmodel import SQLModel

from app import models  # noqa: F401
from app.db.session import Session, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update() -> None:
    with Session(engine):
        SQLModel.metadata.create_all(engine)


def main() -> None:
    logger.info("Updating database tables")
    update()
    logger.info("Database tables updated")


if __name__ == "__main__":
    main()
