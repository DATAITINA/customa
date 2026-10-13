"""Stand photos: checked, stored small, served with long caching (the URL changes per version)."""

import base64
import binascii
import re

from sqlmodel import Session, select

from ..models import StandPhoto, Workspace

MAX_BYTES = 900 * 1024
_DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")
_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


class PhotoError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def decode(data_url: str) -> tuple[str, bytes]:
    match = _DATA_URL.match(data_url.strip())
    if not match:
        raise PhotoError("Send a JPEG, PNG or WebP photo.")
    content_type, payload = match.groups()
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        raise PhotoError("That photo could not be read.")
    if len(raw) > MAX_BYTES:
        raise PhotoError("That photo is too big. Try again, the app shrinks it for you.")
    if not raw.startswith(_MAGIC[content_type]) or (content_type == "image/webp" and raw[8:12] != b"WEBP"):
        raise PhotoError("That file is not a photo.")
    return content_type, raw


def get(session: Session, workspace: Workspace) -> StandPhoto | None:
    return session.exec(select(StandPhoto).where(StandPhoto.workspace_id == workspace.id)).first()


def save(session: Session, workspace: Workspace, data_url: str) -> StandPhoto:
    content_type, raw = decode(data_url)
    row = get(session, workspace)
    if row is None:
        row = StandPhoto(workspace_id=workspace.id, content_type=content_type, data="")
    else:
        row.version += 1
    row.content_type = content_type
    row.data = base64.b64encode(raw).decode()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove(session: Session, workspace: Workspace) -> None:
    row = get(session, workspace)
    if row is not None:
        session.delete(row)
        session.commit()


def photo_path(session: Session, workspace: Workspace) -> str | None:
    """The photo's public path under the API (versioned), or None."""
    version = session.exec(select(StandPhoto.version).where(StandPhoto.workspace_id == workspace.id)).first()
    return f"/public/{workspace.slug}/photo?v={version}" if version else None
