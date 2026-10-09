import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlmodel import Session

from app.actions import account_action as aa
from app.actions import user_action as ua
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import engine as production_engine
from app.initial_data import init, main, should_reset_db
from app.models import Workspace
from app.tests.conftest import engine as test_engine


# 1. Test that `init_db` is called with correct arguments
@patch("app.initial_data.inspect")
@patch("app.initial_data.init_db")
@patch("app.initial_data.Session")
@patch.dict(os.environ, {"INITIAL_DATA_RESET_DB": "false"})
def test_init(mock_session, mock_init_db, mock_inspect):
    # Mock database tables existing
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["workspace"]

    mock_inspect.return_value = mock_inspector

    # Call init function
    init()

    # Check that Session is created and closed
    mock_session.assert_called_once_with(production_engine)

    # Verify `init_db` was called with a non-destructive default.
    mock_init_db.assert_called_once_with(production_engine, create_tables=False)


# 2. Test that empty databases force table creation regardless of env setting
@patch("app.initial_data.inspect")
@patch.dict(os.environ, {"INITIAL_DATA_RESET_DB": "false"})
def test_should_reset_db_when_empty(mock_inspect):
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []
    mock_inspect.return_value = mock_inspector
    assert should_reset_db() is True


@patch("app.initial_data.inspect")
@patch.dict(os.environ, {"INITIAL_DATA_RESET_DB": "false"})
def test_should_reset_db_with_unrelated_tables(mock_inspect):
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["spatial_ref_sys", "some_other_table"]
    mock_inspect.return_value = mock_inspector
    assert should_reset_db() is True


# 3. Test that explicit reset requests bypass database inspection
@patch("app.initial_data.inspect")
@patch.dict(os.environ, {"INITIAL_DATA_RESET_DB": "true"})
def test_should_reset_db_env_override(mock_inspect):
    assert should_reset_db() is True

    # Ensure DB inspection never happens
    mock_inspect.assert_not_called()


# 4. Test Logging Messages
@patch("app.initial_data.logger")
@patch("app.initial_data.init")
def test_main_logging(mock_init, mock_logger):
    # Run main function
    main()

    # Verify logging calls
    mock_logger.info.assert_any_call("Creating initial data")
    mock_logger.info.assert_any_call("Initial data created")
    mock_init.assert_called_once()


def test_init_db_creates_default_workspace_for_superuser() -> None:
    init_db(test_engine, create_tables=True)

    with Session(test_engine) as session:
        account = aa.get_by_email(session, email=settings.FIRST_SUPERUSER)

        assert account is not None
        assert account.current_workspace_id is not None

        workspace = session.get(Workspace, account.current_workspace_id)
        assert workspace is not None
        membership = ua.get_by_all(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
        )
        assert membership is not None
        assert workspace.is_default is True


def test_initial_data_cli_creates_default_workspace_for_superuser() -> None:
    env = os.environ.copy()
    env.update(
        {
            "USE_SQLITE": "true",
            "SQLITE_DATABASE_URI": str(test_engine.url),
            "CORE__USE_SQLITE": "true",
            "CORE__SQLITE_DATABASE_URI": str(test_engine.url),
            "CORE__SQLALCHEMY_DATABASE_URI": "",
            "FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
            "FIRST_SUPERUSER_PASSWORD": settings.FIRST_SUPERUSER_PASSWORD,
            "ACCOUNT__FIRST_SUPERUSER": settings.FIRST_SUPERUSER,
            "ACCOUNT__FIRST_SUPERUSER_PASSWORD": settings.FIRST_SUPERUSER_PASSWORD,
            "INITIAL_DATA_RESET_DB": "true",
        }
    )

    repo_root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [sys.executable, "-m", "app.initial_data"],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    with Session(test_engine) as session:
        account = aa.get_by_email(session, email=settings.FIRST_SUPERUSER)

        assert account is not None
        assert account.current_workspace_id is not None

        workspace = session.get(Workspace, account.current_workspace_id)
        assert workspace is not None
        membership = ua.get_by_all(
            session,
            account_id=account.id,
            workspace_id=workspace.id,
        )
        assert membership is not None
        assert workspace.is_default is True
