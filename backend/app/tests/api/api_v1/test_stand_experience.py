"""The stand's look and install: animal characters, the stand photo, and the Home Screen manifest."""

import base64

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.actions import account_action, user_action
from app.core.config import settings
from app.models import CharacterCreate
from app.services.qr import scan_code
from app.services.stands import create_stand, resolve_stand_settings

SLUG = "panda-stand"
BASE = f"{settings.API_V1_STR}/public/{SLUG}"
VENDOR = f"{settings.API_V1_STR}/stands/{SLUG}"
VENDOR_AUTH = {"Authorization": "Bearer *"}
# The smallest valid JPEG and PNG headers are enough for the server's checks.
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def data_url(raw: bytes, kind: str = "jpeg") -> str:
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode()}"


@pytest.fixture
def stand(session: Session):
    owner = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    workspace, _ = create_stand(
        session,
        owner=owner,
        name="Panda Grill",
        description="Test stand",
        character=CharacterCreate(name="Pandy", body="panda", color="pepper", accessory="chef"),
        slug=SLUG,
    )
    user_action.create_membership(
        session, account_id=owner.id, workspace_id=workspace.id, owner_id=owner.id
    )
    session.commit()
    return workspace


def test_panda_and_friends(client: TestClient, stand) -> None:
    assert client.get(BASE).json()["character"]["body"] == "panda"
    for body in ("chick", "bunny", "cat", "pepper"):
        r = client.put(f"{VENDOR}/character", json={"body": body}, headers=VENDOR_AUTH)
        assert r.status_code == 200, r.text
        assert r.json()["character"]["body"] == body
    assert client.put(f"{VENDOR}/character", json={"body": "dragon"}, headers=VENDOR_AUTH).status_code == 422


def test_stand_photo(client: TestClient, stand) -> None:
    assert client.get(BASE).json()["photo"] is None
    assert client.get(f"{BASE}/photo").status_code == 404

    r = client.put(f"{VENDOR}/photo", json={"data_url": data_url(JPEG)}, headers=VENDOR_AUTH)
    assert r.status_code == 200, r.text
    path = r.json()["photo"]
    assert path == f"/public/{SLUG}/photo?v=1"
    assert client.get(BASE).json()["photo"] == path

    img = client.get(f"{settings.API_V1_STR}{path}")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg" and img.content == JPEG
    assert "immutable" in img.headers["cache-control"]

    # A new photo gets a new URL, so phones never keep the old one.
    r = client.put(f"{VENDOR}/photo", json={"data_url": data_url(PNG, "png")}, headers=VENDOR_AUTH)
    assert r.json()["photo"].endswith("?v=2")

    assert client.delete(f"{VENDOR}/photo", headers=VENDOR_AUTH).json()["photo"] is None


def test_photo_checks(client: TestClient, stand) -> None:
    bad = [
        data_url(b"not an image at all, just text" * 5),  # says jpeg, is not
        "data:image/svg+xml;base64," + base64.b64encode(b"<svg></svg>" * 10).decode(),
        data_url(b"\xff\xd8\xff" + b"\x00" * (901 * 1024)),  # too big
    ]
    for payload in bad:
        r = client.put(f"{VENDOR}/photo", json={"data_url": payload}, headers=VENDOR_AUTH)
        assert r.status_code in (400, 422), payload[:40]
    assert client.put(f"{VENDOR}/photo", json={"data_url": data_url(JPEG)}).status_code == 401


def test_home_screen_manifest_opens_the_stand_with_the_card(client: TestClient, session: Session, stand) -> None:
    scan = scan_code(stand, resolve_stand_settings(session, stand))
    key = client.post(f"{BASE}/visits", json={"consent": True, "scan": scan}).json()["customer"]["key"]

    r = client.get(f"{BASE}/manifest", params={"k": key})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["start_url"] == f"/s/{SLUG}?app=1&k={key}"
    assert m["id"] == f"/s/{SLUG}" and m["display"] == "standalone"
    assert m["short_name"] == "Panda Grill"

    # Unknown or odd keys never go into the start URL.
    for k in ("not-a-customer-key-123", "<script>", ""):
        assert client.get(f"{BASE}/manifest", params={"k": k}).json()["start_url"] == f"/s/{SLUG}?app=1"
    assert client.get(f"{BASE}/manifest").json()["start_url"] == f"/s/{SLUG}?app=1"


def test_stand_view_lists_features(client: TestClient, stand) -> None:
    features = client.get(BASE).json()["features"]
    assert features == {"plate_ajo": False, "lunch_crew": False, "alerts": False, "prize_wheel": False}
