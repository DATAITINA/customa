import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.mark.skip(reason="Celery not yet configured")
def test_celery_worker_test(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    data = {"msg": "test"}
    r = client.post(
        f"{settings.API_V1_STR}/utils/test-celery/",
        json=data,
        headers=superuser_account_token_headers,
    )
    response = r.json()
    assert response["msg"] == "Word received"
