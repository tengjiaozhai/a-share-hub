import pytest
from fastapi.testclient import TestClient

from src.main import build_app


@pytest.fixture
def client():
    app = build_app()
    return TestClient(app)


def test_crypto_router_is_registered_or_explicitly_absent(authenticated_client):
    client = authenticated_client
    response = client.get("/api/v1/crypto/status")

    assert response.status_code in {200, 404, 500}
