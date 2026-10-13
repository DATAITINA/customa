"""The stand's QR code carries a secret scan code, so a plate counts only after a real scan.

Opening the stand page from a bookmark, the browser history or a shared link shows the card but
counts nothing: the count routes need the code that is only printed in the stand's QR code
(or shown on the vendor's QR page). The code is derived from the server secret, so nothing is
stored; QR_VERSION lets the vendor make a new QR code, which turns every older print off.
"""

import hashlib
import hmac

from ..core.config import CustomaSettings, settings
from ..models import Workspace


def scan_code(workspace: Workspace, stand_settings: CustomaSettings) -> str:
    message = f"customa-qr:{workspace.id}:{stand_settings.QR_VERSION}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()
    return digest[:16]


def is_genuine_scan(code: str | None, workspace: Workspace, stand_settings: CustomaSettings) -> bool:
    if not code:
        return False
    return hmac.compare_digest(code.strip().lower(), scan_code(workspace, stand_settings))
