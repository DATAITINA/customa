"""Stand photos: checked, stored small, served with long caching (the URL changes per version).

Two homes, one rule set:
- MSFLib drivelink (STAND_PHOTOS_IN_DRIVELINK on, with cloud storage such as Cloudinary): the
  photo is a file in the vendor's drive, folder "Stand photos · <stand>", uploaded through
  DrivelinkService (its upload checks, storage and quota); StandPhotoFile points at the node.
- Otherwise the database (StandPhoto), as before. Vercel can't keep files, so this is the
  default until cloud storage is set up.
"""

import base64
import binascii
import io
import re

from fastapi import UploadFile
from msflib.drivelink.models import DrivelinkKind, DrivelinkNode
from msflib.drivelink.services import DrivelinkService
from msflib.utils.uploads import StorageBlob, StorageMethod
from sqlmodel import Session, select
from starlette.datastructures import Headers

from ..core.config import settings
from ..models import StandPhoto, StandPhotoFile, Workspace

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

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


def in_drivelink() -> bool:
    return bool(settings.STAND_PHOTOS_IN_DRIVELINK)


def drive_file(session: Session, workspace: Workspace) -> StandPhotoFile | None:
    return session.exec(select(StandPhotoFile).where(StandPhotoFile.workspace_id == workspace.id)).first()


def _folder(drive: DrivelinkService, session: Session, workspace: Workspace, account_id: int) -> DrivelinkNode:
    """The stand's "Stand photos" folder in the vendor's drive (made on first upload)."""
    name = f"Stand photos · {workspace.slug}"
    for node in drive.action.list_children(session, account_id=account_id, parent_id=None, workspace_id=workspace.id, limit=None):
        if node.kind == DrivelinkKind.folder and node.name == name:
            return node
    return drive.action.create_folder(session, account_id=account_id, parent_id=None, name=name, workspace_id=workspace.id)


def _save_in_drivelink(session: Session, workspace: Workspace, account_id: int, content_type: str, raw: bytes) -> StandPhotoFile:
    drive = DrivelinkService(settings)
    folder = _folder(drive, session, workspace, account_id)
    row = drive_file(session, workspace)
    version = (row.version + 1) if row else 1
    upload = UploadFile(io.BytesIO(raw), filename=f"stand-photo-v{version}{EXT[content_type]}",
                        headers=Headers({"content-type": content_type}))
    node = drive.create_file(session, upload, parent_id=folder.id, account_id=account_id, workspace_id=workspace.id)
    if row is not None:
        _delete_node(session, workspace, row)
        row.node_id, row.account_id, row.version = node.id, account_id, version
    else:
        row = StandPhotoFile(workspace_id=workspace.id, node_id=node.id, account_id=account_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _delete_node(session: Session, workspace: Workspace, row: StandPhotoFile) -> None:
    """Remove the old photo file from the drive and its storage."""
    DrivelinkService(settings).action.hard_delete(
        session, node_id=row.node_id, account_id=row.account_id, settings=settings, workspace_id=workspace.id, commit=False
    )


def read(session: Session, workspace: Workspace) -> tuple[str, bytes | None, str | None] | None:
    """(content type, bytes, or a public URL to redirect to) for the stand photo, or None."""
    row = drive_file(session, workspace)
    if row is not None:
        node = session.get(DrivelinkNode, row.node_id)
        if node is not None and node.storage_method:
            if node.storage_url and node.storage_url.startswith("https://"):
                return node.mime_type or "image/jpeg", None, node.storage_url
            blob = StorageBlob(url=node.storage_url or "", storage_method=node.storage_method,
                               parent_folder=node.storage_parent_folder or "", storage_bucket=node.storage_bucket or "",
                               filename=node.storage_filename or "", content_type=node.mime_type)
            return node.mime_type or "image/jpeg", StorageMethod.storage_from_blob(blob, settings).read_blob_bytes(blob), None
    photo = get(session, workspace)
    return (photo.content_type, base64.b64decode(photo.data), None) if photo else None


def save(session: Session, workspace: Workspace, data_url: str, account_id: int | None = None) -> None:
    content_type, raw = decode(data_url)
    if in_drivelink() and account_id is not None:
        _save_in_drivelink(session, workspace, account_id, content_type, raw)
        old = get(session, workspace)
        if old is not None:  # the database copy is replaced by the drive file
            session.delete(old)
            session.commit()
        return
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
    file_row = drive_file(session, workspace)
    if file_row is not None:
        _delete_node(session, workspace, file_row)
        session.delete(file_row)
    row = get(session, workspace)
    if row is not None:
        session.delete(row)
    session.commit()


def photo_path(session: Session, workspace: Workspace) -> str | None:
    """The photo's public path under the API (versioned), or None."""
    file_version = session.exec(select(StandPhotoFile.version).where(StandPhotoFile.workspace_id == workspace.id)).first()
    if file_version:
        return f"/public/{workspace.slug}/photo?v=d{file_version}"
    version = session.exec(select(StandPhoto.version).where(StandPhoto.workspace_id == workspace.id)).first()
    return f"/public/{workspace.slug}/photo?v={version}" if version else None
