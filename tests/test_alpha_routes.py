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
