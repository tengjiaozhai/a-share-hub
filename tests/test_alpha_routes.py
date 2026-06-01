from fastapi.testclient import TestClient
from src.main import build_app


def test_alpha_assets_endpoint_returns_normalized_rows(monkeypatch):
    from src.api import routes_alpha

    class FakeService:
        async def list_asset_snapshots(self):
            from src.alpha.models import AlphaAssetSnapshot
            return [
                AlphaAssetSnapshot(
                    symbol="AAPLx",
                    underlying_symbol="AAPL",
                    project_id="alpha-aaplx",
                    market_status="TRADING",
                    asset_status="ACTIVE",
                    shares_multiplier=1.0,
                    min_qty=0.1,
                    max_qty=50.0,
                )
            ]

    async def override_get_alpha_service():
        return FakeService()

    app = build_app()
    app.dependency_overrides[routes_alpha.get_alpha_service] = override_get_alpha_service
    client = TestClient(app)

    response = client.get("/api/v1/alpha/assets")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["symbol"] == "AAPLx"
    assert body["items"][0]["market_status"] == "TRADING"


def test_alpha_ticket_api_supports_create_approve_and_fill(test_app):
    client = TestClient(test_app)

    create_res = client.post(
        "/api/v1/alpha/tickets",
        json={
            "asset_symbol": "AAPLx",
            "underlying_symbol": "AAPL",
            "action": "BUY",
            "thesis": "discount to reference",
            "suggested_quantity": 2.0,
            "suggested_limit_price": 210.5,
            "expires_at": "2026-06-01T16:00:00+08:00",
        },
    )
    ticket_id = create_res.json()["ticket_id"]

    approve_res = client.post(f"/api/v1/alpha/tickets/{ticket_id}/approve", json={"operator_id": "trader-01"})
    fill_res = client.post(
        f"/api/v1/alpha/tickets/{ticket_id}/fills",
        json={
            "operator_id": "trader-01",
            "executed_quantity": 2.0,
            "executed_price": 210.2,
            "notes": "filled manually",
        },
    )
    workbench_res = client.get("/api/v1/dashboard/workbench")

    assert create_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"
    assert fill_res.json()["recorded"] is True
    assert "alpha" in workbench_res.json()
    assert workbench_res.json()["alpha"]["tickets"][0]["asset_symbol"] == "AAPLx"
