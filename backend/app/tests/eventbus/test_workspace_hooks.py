from msflib.eventbus import use_app_emitter
from sqlmodel import Session

from app.actions import account_action, user_action
from app.main import app


def test_new_account_gets_default_workspace_membership(session: Session) -> None:
    with use_app_emitter(app):
        account = account_action.create(session, data=account_action.random())

    memberships = user_action.get_multi_by_all(session, account_id=account.id, limit=100)

    assert len(memberships) == 1
