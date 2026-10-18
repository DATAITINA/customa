"""Google sign-in (MSFLib auth): a new Google email becomes a vendor account through the
google-account-create listener, and the session middleware Google's login step needs is on."""

from msflib.auth.models.schema import GoogleUserInfo
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.actions import account_action
from app.main import app, app_emitter


def test_new_google_email_becomes_a_vendor_account(session: Session):
    info = GoogleUserInfo(email="New.Vendor@Example.com", name="New Vendor")
    app_emitter.emit_required("google-account-create", info, {"session": session})
    account = account_action.get_by_email(session, email="new.vendor@example.com")
    assert account is not None and account.hashed_password


def test_session_middleware_is_installed():
    assert any(m.cls is SessionMiddleware for m in app.user_middleware)
