import os
from collections.abc import Generator
from pathlib import Path

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from msflib.core.store import MapStore
from msflib.utils.tests.account import (
    account_authentication_headers,
    authentication_token_from_email,
)
from sqlmodel import Session, create_engine

from app.actions import account_action
from app.api.deps import get_keystore, get_session
from app.core.config import settings
from app.db.init_db import init_db
from app.main import app

worker_id = os.getenv("PYTEST_XDIST_WORKER", "default")
if worker_id == "default":
    TEST_DATABASE_URL = "sqlite:///./tmp/test.db"
else:
    TEST_DATABASE_URL = f"sqlite:///./tmp/test_{worker_id}.db"

DUMP_DB_QUERIES = False  # change to True to display all DB SQL queries

Path("tmp").mkdir(parents=True, exist_ok=True)

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    echo=DUMP_DB_QUERIES,
)


# These two event listeners are only needed for sqlite for proper
# SAVEPOINT / nested transaction support. Other databases like postgres
# don't need them.
# From: https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl  # noqa: E501
# @sa.event.listens_for(engine, "connect")
# def do_connect(dbapi_connection, connection_record):
#     # disable pysqlite's emitting of the BEGIN statement entirely.
#     # also stops it from emitting COMMIT before any DDL.
#     dbapi_connection.isolation_level = None


# @sa.event.listens_for(engine, "begin")
# def do_begin(conn):
#     # emit our own BEGIN
#     conn.exec_driver_sql("BEGIN")


@pytest.fixture(scope="function")
def session() -> Generator:
    init_db(engine, create_tables=True)
    with Session(engine) as session:
        yield session


# @pytest.fixture(scope="session")
# def _session() -> Generator:
#     # with Session(engine) as session:
#     #     yield session
#     connection = engine.connect()
#     transaction = connection.begin()
#     # session = TestingSessionLocal(bind=connection)
#     session = Session(connection)

#     # Begin a nested transaction (using SAVEPOINT).
#     nested = connection.begin_nested()

#     # If the application code calls session.commit, it will end the nested
#     # transaction. Need to start a new one when that happens.
#     @sa.event.listens_for(session, "after_transaction_end")
#     def end_savepoint(session, transaction):
#         nonlocal nested
#         if not nested.is_active:
#             nested = connection.begin_nested()

#     yield session

#     # Rollback the overall transaction, restoring the state before the test ran.
#     session.close()
#     transaction.rollback()
#     connection.close()


class MockMapStore(MapStore):
    def clear(self):
        self.store = set()


@pytest.fixture(scope="function")
def mapstore() -> Generator:
    yield MockMapStore()


# A fixture for the fastapi test client which depends on the
# previous session fixture. Instead of creating a new session in the
# dependency override as before, it uses the one provided by the
# session fixture.
@pytest.fixture(scope="function")
def client(session, mapstore) -> Generator:
    def override_get_session():
        yield session

    def override_get_keystore():
        return mapstore

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_keystore] = override_get_keystore

    yield TestClient(app)
    del app.dependency_overrides[get_session]
    del app.dependency_overrides[get_keystore]


@pytest.fixture(scope="function")
def superuser_account_token_headers(client: TestClient) -> dict[str, str]:
    return account_authentication_headers(
        client=client,
        email=settings.FIRST_SUPERUSER,
        password=settings.FIRST_SUPERUSER_PASSWORD,
        oauth_url=f"{settings.API_V1_STR}/login",
    )


@pytest.fixture(scope="function")
def normal_account_token_headers(client: TestClient, session: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client,
        email=settings.EMAIL_TEST_ACCOUNT,
        session=session,
        account_action=account_action,
        oauth_url=f"{settings.API_V1_STR}/login",
    )


@pytest.fixture(scope="session")
def faker() -> Faker:
    return Faker()


@pytest.fixture(scope="function")
def mock_send_email(mocker):
    return mocker.patch("msflib.services.email.send_email", return_value=None)
