"""A photo of the vendor's food stand (one per stand), shown on the customer page and QR sign.

The phone shrinks the photo before upload (about 1280 px, JPEG), so rows stay small.
Migration: scripts/migrations/2026-10-14_stand_photo.sql.
"""

from msflib.models import ModelBase
from sqlmodel import Field


class StandPhoto(ModelBase, table=True):
    workspace_id: int = Field(foreign_key="workspace.id", unique=True, index=True)
    content_type: str  # image/jpeg, image/png or image/webp
    data: str  # base64
    version: int = 1  # part of the public URL, so phones can cache each version for good


class StandPhotoFile(ModelBase, table=True):
    """The stand photo kept as a file in the vendor's MSFLib drivelink drive (folder "Stand
    photos"), when STAND_PHOTOS_IN_DRIVELINK is on (cloud storage set up). New table only
    (migration 2026-10-20_drivelink_stand_photos.sql)."""

    workspace_id: int = Field(foreign_key="workspace.id", unique=True, index=True)
    node_id: int = Field(foreign_key="drivelinknode.id")
    account_id: int  # the drive's owner (the vendor who uploaded it)
    version: int = 1
