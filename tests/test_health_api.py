from fastapi.testclient import TestClient

from src.main import build_app


client = TestClient(build_app())


def test_health_liveness_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_returns_ok_when_probe_succeeds(monkeypatch):
    from src.api import routes_health

    monkeypatch.setattr(
        routes_health,
        "probe_runtime_database_from_settings",
        lambda: {"ok": True, "latency_ms": 3.2},
    )
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["latency_ms"] == 3.2


def test_health_ready_returns_503_when_probe_fails(monkeypatch):
    from src.api import routes_health

    monkeypatch.setattr(
        routes_health,
        "probe_runtime_database_from_settings",
        lambda: {"ok": False, "error": "connect failed"},
    )
    response = client.get("/health/ready")
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["ok"] is False
    assert "connect failed" in detail["error"]
