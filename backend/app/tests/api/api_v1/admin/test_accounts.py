from fastapi.testclient import TestClient

from app.core.config import settings


def test_admin_accounts_list_smoke(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/admin/accounts/",
        headers=superuser_account_token_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(account["email"] == settings.FIRST_SUPERUSER.lower() for account in payload)
