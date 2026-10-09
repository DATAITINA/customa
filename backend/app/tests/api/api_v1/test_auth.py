from fastapi.testclient import TestClient

from app.core.config import settings


def test_use_access_token(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert result["email"] == settings.FIRST_SUPERUSER.lower()


def test_clear_access_token(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    assert r.status_code == 200

    r1 = client.delete(
        f"{settings.API_V1_STR}/logout",
        headers=superuser_account_token_headers,
    )
    assert r1.status_code == 200

    r2 = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    assert r2.status_code in {401, 403}

    r3 = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": settings.FIRST_SUPERUSER.upper(),
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert r3.status_code == 200
    token = r3.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r4 = client.get(
        f"{settings.API_V1_STR}/me",
        headers=headers,
    )
    assert r4.status_code == 200
