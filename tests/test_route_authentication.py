from fastapi.testclient import TestClient


PROTECTED_GETS = (
    "/api/v1/dashboard/workbench",
    "/api/v1/market/stocks",
    "/api/v1/alpha/portfolio",
    "/api/v1/us-stock/watchlist",
    "/api/v1/a-stock/watchlist",
    "/api/v1/decision-runs",
    "/api/v1/execution-plans/ready",
    "/api/v1/portfolio-targets/active",
    "/api/v1/reconciliation/status",
    "/api/v1/kill-switch/status",
    "/api/v1/crypto/status",
)


def test_protected_routers_reject_anonymous_requests(test_app):
    client = TestClient(test_app)
    for path in PROTECTED_GETS:
        assert client.get(path).status_code == 401, path


def test_broker_callback_is_not_cookie_authenticated(test_app):
    client = TestClient(test_app)
    response = client.post("/api/v1/broker-events", content=b"{}")
    assert response.status_code != 401 or response.json()["detail"] == "invalid broker signature"
