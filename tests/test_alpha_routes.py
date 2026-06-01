from fastapi.testclient import TestClient
from src.main import build_app
from src.api import routes_alpha


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
    assert create_res.status_code == 200
    ticket_id = create_res.json()["ticket_id"]

    approve_res = client.post(f"/api/v1/alpha/tickets/{ticket_id}/approve", json={"operator_id": "trader-01"})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    fill_res = client.post(
        f"/api/v1/alpha/tickets/{ticket_id}/fills",
        json={
            "operator_id": "trader-01",
            "executed_quantity": 2.0,
            "executed_price": 210.2,
            "notes": "filled manually",
        },
    )
    assert fill_res.status_code == 200
    assert fill_res.json()["recorded"] is True

    workbench_res = client.get("/api/v1/dashboard/workbench")
    assert workbench_res.status_code == 200
    assert "alpha" in workbench_res.json()
    assert workbench_res.json()["alpha"]["tickets"][0]["asset_symbol"] == "AAPLx"


def test_alpha_ticket_api_returns_404_for_nonexistent_ticket(test_app):
    client = TestClient(test_app)

    approve_res = client.post(
        "/api/v1/alpha/tickets/nonexistent-ticket/approve",
        json={"operator_id": "trader-01"},
    )
    assert approve_res.status_code == 404

    fill_res = client.post(
        "/api/v1/alpha/tickets/nonexistent-ticket/fills",
        json={
            "operator_id": "trader-01",
            "executed_quantity": 2.0,
            "executed_price": 210.2,
            "notes": "filled manually",
        },
    )
    assert fill_res.status_code == 404


def test_alpha_reconciliation_route_returns_run_id(test_app, pg_store):
    pg_store.replace_alpha_positions(
        [{"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0}]
    )
    pg_store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=28.8,
        nav=8_798.8,
    )
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/alpha/reconciliation/run",
        json={"external_positions": {"AAPLx": 1.0}, "external_cash": 8_420.0},
    )

    assert response.status_code == 200
    assert response.json()["run_id"].startswith("alpha-recon-")
    assert response.json()["status"] == "MISMATCH"


def test_alpha_watchlist_api_supports_list_and_add():
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.list_alpha_watchlist_items.return_value = [
        {"symbol": "AAPLx", "underlying_symbol": "AAPL", "priority": 1}
    ]

    from src.storage.dependencies import get_runtime_store

    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: mock_store
    client = TestClient(app)

    add_res = client.post(
        "/api/v1/alpha/watchlist",
        json={"symbol": "AAPLx", "underlying_symbol": "AAPL", "priority": 1},
    )
    assert add_res.status_code == 200
    assert add_res.json()["stored"] is True
    assert add_res.json()["symbol"] == "AAPLx"
    mock_store.add_alpha_watchlist_item.assert_called_once_with(symbol="AAPLx", underlying_symbol="AAPL", priority=1)

    list_res = client.get("/api/v1/alpha/watchlist")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "AAPLx"


def test_alpha_research_scan_endpoint_returns_ranked_candidates():
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.list_alpha_watchlist_items.return_value = [
        {"symbol": "AAPLx", "underlying_symbol": "AAPL", "priority": 1},
        {"symbol": "SPYx", "underlying_symbol": "SPY", "priority": 2},
    ]

    from src.storage.dependencies import get_runtime_store

    class FakeResearchService:
        async def rank_watchlist(self, symbols: list[str]) -> list[dict]:
            return [
                {"symbol": "AAPLx", "score": 0.1, "action": "BUY", "reason": "trend=0.02, momentum=0.09"},
                {"symbol": "SPYx", "score": -0.1, "action": "SELL", "reason": "trend=-0.01, momentum=-0.02"},
            ]

    async def override_get_alpha_research_service():
        return FakeResearchService()

    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: mock_store
    app.dependency_overrides[routes_alpha.get_alpha_research_service] = override_get_alpha_research_service
    client = TestClient(app)

    response = client.post("/api/v1/alpha/research/scan")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["symbol"] == "AAPLx"
    assert items[0]["action"] == "BUY"
    assert items[1]["symbol"] == "SPYx"
    assert items[1]["action"] == "SELL"


def test_alpha_research_candidate_can_be_promoted_to_ticket(test_app, pg_store, monkeypatch):
    from src.api import routes_alpha

    class FakeResearchService:
        async def rank_watchlist(self, symbols):
            return [{"symbol": "AAPLx", "action": "BUY", "score": 0.8, "reason": "trend strong"}]

        def build_ticket_from_signal(self, signal, thesis_prefix):
            return {
                "asset_symbol": "AAPLx",
                "underlying_symbol": "AAPL",
                "action": "BUY",
                "thesis": f"{thesis_prefix}: trend strong",
                "suggested_quantity": 1.0,
                "suggested_limit_price": 0.0,
            }

    async def override_get_alpha_research_service():
        yield FakeResearchService()

    test_app.dependency_overrides[routes_alpha.get_alpha_research_service] = override_get_alpha_research_service
    pg_store.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    client = TestClient(test_app)

    response = client.post("/api/v1/alpha/research/propose-top-ticket", json={"thesis_prefix": "auto"})

    assert response.status_code == 200
    assert response.json()["asset_symbol"] == "AAPLx"
    assert response.json()["ticket_id"].startswith("alpha-ticket-")


def test_alpha_capabilities_report_manual_mode(monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())

    app = build_app()
    client = TestClient(app)

    response = client.get("/api/v1/alpha/capabilities")

    assert response.status_code == 200
    assert response.json()["mode"] == "manual"


def test_alpha_submit_returns_409_when_capability_disabled(monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

        def build_submission(self, request):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())

    app = build_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/alpha/orders/submit",
        json={
            "ticket_id": "alpha-ticket-001",
            "asset_symbol": "AAPLx",
            "action": "BUY",
            "quantity": 1.0,
            "limit_price": 210.0,
        },
    )

    assert response.status_code == 409
