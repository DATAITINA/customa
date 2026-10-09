"""POST /logout for @msflib/react-auth.

The React auth package signs out with POST, while MSFLib's auth router serves
DELETE /logout. This route does the same thing (MSFLib's revoke_access_token)
and returns JSON, because the frontend client parses every response as JSON.
"""

from fastapi import APIRouter, Depends
from msflib.core.security import revoke_access_token
from msflib.core.store import StoreInterface

from app.api import deps
from app.models import Account

router = APIRouter(tags=["auth"])


@router.post("/logout")
def logout(
    account: Account = Depends(deps.get_current_account),
    token_store: StoreInterface = Depends(deps.get_keystore),
) -> dict[str, bool]:
    revoke_access_token(token_store, account.email)
    return {"ok": True}
