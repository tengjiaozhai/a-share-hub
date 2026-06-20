from fastapi.testclient import TestClient

from src.alpha.portfolio_service import AlphaPortfolioService
from src.api import routes_alpha
from src.main import build_app


def test_alpha_assets_endpoint_returns_normalized_rows(authenticated_client, test_app, monkeypatch):
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
                    shares_multiplier=0.1,
                    min_qty=0.1,
                    max_qty=50.0,
                )
            ]

    async def override_get_alpha_service():
        return FakeService()

    test_app.dependency_overrides[routes_alpha.get_alpha_service] = override_get_alpha_service
    client = authenticated_client

    response = client.get("/api/v1/alpha/assets")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["symbol"] == "AAPLx"
    assert body["items"][0]["market_status"] == "TRADING"


def test_alpha_ticket_api_supports_create_approve_and_fill(authenticated_client, test_app):
    client = authenticated_client

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
            "executed_at": "2026-06-01T10:30:00+08:00",
            "notes": "filled manually",
        },
    )
    assert fill_res.status_code == 200
    assert fill_res.json()["recorded"] is True
    assert fill_res.json()["portfolio_rebuilt"] is False

    portfolio_res = client.get("/api/v1/alpha/portfolio")
    assert portfolio_res.status_code == 200
    portfolio = portfolio_res.json()
    assert portfolio["fills"][0]["ticket_id"] == ticket_id
    assert portfolio["fills"][0]["asset_symbol"] == "AAPLx"
    assert portfolio["fills"][0]["action"] == "BUY"
    assert portfolio["fills"][0]["executed_at"] == "2026-06-01T10:30:00+08:00"

    workbench_res = client.get("/api/v1/dashboard/workbench")
    assert workbench_res.status_code == 200
    assert "alpha" in workbench_res.json()
    assert workbench_res.json()["alpha"]["tickets"][0]["asset_symbol"] == "AAPLx"


def test_alpha_ticket_api_returns_404_for_nonexistent_ticket(authenticated_client, test_app):
    client = authenticated_client

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


def test_alpha_reconciliation_route_returns_run_id(authenticated_client, test_app, pg_store):
    pg_store.replace_alpha_positions(
        positions=[{"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0}],
    )
    pg_store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=28.8,
        nav=8_798.8,
    )
    client = authenticated_client

    response = client.post(
        "/api/v1/alpha/reconciliation/run",
        json={"external_positions": {"AAPLx": 1.0}, "external_cash": 8_420.0},
    )

    assert response.status_code == 200
    assert response.json()["run_id"].startswith("alpha-recon-")
    assert response.json()["status"] == "MISMATCH"


def test_alpha_watchlist_api_supports_list_and_add(authenticated_client, test_app, ):
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.list_alpha_watchlist_items.return_value = [
        {"symbol": "AAPLx", "underlying_symbol": "AAPL", "priority": 1}
    ]

    from src.api.dependencies import get_user_runtime_store

    test_app.dependency_overrides[get_user_runtime_store] = lambda: mock_store
    client = authenticated_client

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


def test_alpha_research_scan_endpoint_returns_ranked_candidates(authenticated_client, test_app, ):
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.list_alpha_watchlist_items.return_value = [
        {"symbol": "AAPLx", "underlying_symbol": "AAPL", "priority": 1},
        {"symbol": "SPYx", "underlying_symbol": "SPY", "priority": 2},
    ]
    mock_store.list_alpha_positions.return_value = [
        {"symbol": "AAPLx", "quantity": 1.5, "avg_cost": 205.0, "mark_price": 211.0}
    ]

    from src.api import routes_alpha
    from src.api.dependencies import get_user_runtime_store

    class FakeResearchService:
        async def rank_watchlist(self, symbols: list[str]) -> list[dict]:
            return [
                {"symbol": "AAPLx", "score": 0.1, "action": "BUY", "reason": "trend=0.02, momentum=0.09"},
                {"symbol": "SPYx", "score": -0.1, "action": "SELL", "reason": "trend=-0.01, momentum=-0.02"},
            ]

    async def override_get_alpha_research_service():
        return FakeResearchService()

    test_app.dependency_overrides[get_user_runtime_store] = lambda: mock_store
    test_app.dependency_overrides[routes_alpha.get_alpha_research_service] = override_get_alpha_research_service
    client = authenticated_client

    response = client.post("/api/v1/alpha/research/scan")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["symbol"] == "AAPLx"
    assert items[0]["action"] == "BUY"
    assert items[0]["is_held"] is True
    assert items[0]["held_quantity"] == 1.5
    assert items[0]["portfolio_guidance"] == "add_or_watch"
    assert items[1]["symbol"] == "SPYx"
    assert items[1]["action"] == "SELL"
    assert items[1]["is_held"] is False
    assert items[1]["portfolio_guidance"] == "ignore_no_position"


def test_alpha_portfolio_rebuild_endpoint_rebuilds_from_all_fills(authenticated_client, test_app, pg_store):
    buy_ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="open position",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    sell_ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="SELL",
        thesis="trim position",
        suggested_quantity=0.5,
        suggested_limit_price=210.0,
        expires_at="2026-06-01T16:30:00+08:00",
    )
    pg_store.insert_alpha_manual_fill(
        ticket_id=buy_ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )
    pg_store.insert_alpha_manual_fill(
        ticket_id=sell_ticket_id,
        operator_id="trader-01",
        executed_quantity=0.5,
        executed_price=210.0,
        notes="sell fill",
    )
    client = authenticated_client

    response = client.post(
        "/api/v1/alpha/portfolio/rebuilds",
        json={"opening_cash": 10_000.0, "price_map": {"AAPLx": 215.0}},
    )

    assert response.status_code == 200
    portfolio = response.json()
    assert round(portfolio["snapshot"]["cash_balance"], 2) == 9_705.0
    assert round(portfolio["snapshot"]["realized_pnl"], 2) == 5.0
    assert round(portfolio["snapshot"]["unrealized_pnl"], 2) == 22.5
    assert round(portfolio["snapshot"]["nav"], 2) == 10_027.5
    assert portfolio["positions"][0]["symbol"] == "AAPLx"
    assert round(portfolio["positions"][0]["quantity"], 2) == 1.5
    assert len(portfolio["fills"]) == 2


def test_alpha_fill_can_rebuild_portfolio_immediately(authenticated_client, test_app, pg_store):
    ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="open position",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    client = authenticated_client

    response = client.post(
        f"/api/v1/alpha/tickets/{ticket_id}/fills",
        json={
            "operator_id": "trader-01",
            "executed_quantity": 2.0,
            "executed_price": 200.0,
            "executed_at": "2026-06-01T10:30:00+08:00",
            "notes": "buy fill",
            "rebuild_opening_cash": 10_000.0,
            "rebuild_price_map": {"AAPLx": 215.0},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recorded"] is True
    assert body["portfolio_rebuilt"] is True
    assert round(body["portfolio"]["snapshot"]["nav"], 2) == 10_030.0
    assert body["portfolio"]["positions"][0]["symbol"] == "AAPLx"
    assert body["portfolio"]["fills"][0]["executed_at"] == "2026-06-01T10:30:00+08:00"


def test_alpha_research_candidate_can_be_promoted_to_ticket(authenticated_client, test_app, pg_store, monkeypatch):
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
    client = authenticated_client

    response = client.post("/api/v1/alpha/research/propose-top-ticket", json={"thesis_prefix": "auto"})

    assert response.status_code == 200
    assert response.json()["asset_symbol"] == "AAPLx"
    assert response.json()["ticket_id"].startswith("alpha-ticket-")


def test_alpha_capabilities_report_manual_mode(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())

    app = build_app()
    client = authenticated_client

    response = client.get("/api/v1/alpha/capabilities")

    assert response.status_code == 200
    assert response.json()["mode"] == "manual"


def test_generate_portfolio_report_endpoint(authenticated_client, test_app, pg_store):
    ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="open position",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    pg_store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )
    AlphaPortfolioService(pg_store, user_id="test-user").rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0},
    )
    client = authenticated_client

    response = client.post(
        "/api/v1/alpha/portfolio/report",
        json={
            "symbols": ["AAPLx"],
            "opening_cash": 10_000.0,
            "positions": [
                {
                    "symbol": "AAPLx",
                    "lots": [
                        {
                            "buy_date": "2026-06-01T09:30:00+08:00",
                            "buy_price": 200.0,
                            "quantity": 2.0,
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    assert "portfolio_snapshot" in body
    assert body["analysis_input"] == {
        "symbols": ["AAPLx"],
        "positions": [
            {
                "symbol": "AAPLx",
                "lots": [
                    {
                        "buy_date": "2026-06-01T09:30:00+08:00",
                        "buy_price": 200.0,
                        "quantity": 2.0,
                    }
                ],
            }
        ],
    }
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["symbol"] == "AAPLx"
    assert item["unrealized_pnl"] == 20.0
    assert item["analysis_context"] == {
        "lot_count": 1,
        "total_quantity": 2.0,
        "total_cost": 400.0,
        "weighted_avg_cost": 200.0,
        "first_buy_date": "2026-06-01T09:30:00+08:00",
        "last_buy_date": "2026-06-01T09:30:00+08:00",
    }
    assert item["recommendation"]["action"] in {"HOLD", "ADD", "REDUCE", "EXIT", "WATCH"}


def test_generate_portfolio_report_endpoint_normalizes_symbols_before_service(
    authenticated_client,
    test_app,
    monkeypatch,
):
    captured_payload = {}

    class FakeReportService:
        def __init__(self, store, user_id=None):
            self.store = store
            self.user_id = user_id

        def generate_report(self, payload):
            captured_payload.update(payload)
            return {
                "generated_at": "2026-06-20T12:00:00+08:00",
                "portfolio_snapshot": {},
                "backtest_window": payload["backtest_window"],
                "analysis_input": {
                    "symbols": payload["symbols"],
                    "positions": payload["positions"],
                },
                "items": [],
            }

    monkeypatch.setattr(routes_alpha, "AlphaPortfolioReportService", FakeReportService)
    client = authenticated_client

    response = client.post(
        "/api/v1/alpha/portfolio/report",
        json={
            "symbols": ["600519", "msft", "NVDA.US", "000001.SZ"],
            "positions": [
                {
                    "symbol": "600519",
                    "lots": [
                        {"buy_date": "2026-06-20", "buy_price": 1500, "quantity": 100},
                    ],
                },
                {
                    "symbol": "msft",
                    "lots": [
                        {"buy_date": "2026-06-18", "buy_price": 420.5, "quantity": 2},
                        {"buy_date": "2026-06-19", "buy_price": 425.0, "quantity": 1},
                    ],
                },
            ],
            "include_shadow": True,
            "include_backtest": True,
            "backtest_window": "60d",
            "opening_cash": 10_000.0,
        },
    )

    assert response.status_code == 200
    assert captured_payload["symbols"] == ["600519.SH", "MSFT.US", "NVDA.US", "000001.SZ"]
    assert captured_payload["positions"] == [
        {
            "symbol": "600519.SH",
            "lots": [
                {"buy_date": "2026-06-20", "buy_price": 1500.0, "quantity": 100.0},
            ],
        },
        {
            "symbol": "MSFT.US",
            "lots": [
                {"buy_date": "2026-06-18", "buy_price": 420.5, "quantity": 2.0},
                {"buy_date": "2026-06-19", "buy_price": 425.0, "quantity": 1.0},
            ],
        },
    ]


def test_generate_portfolio_report_endpoint_returns_analysis_context_for_requested_symbols(
    authenticated_client,
    test_app,
    monkeypatch,
):
    class FakeReportService:
        def __init__(self, store, user_id=None):
            self.store = store
            self.user_id = user_id

        def generate_report(self, payload):
            return {
                "generated_at": "2026-06-20T12:00:00+08:00",
                "portfolio_snapshot": {},
                "backtest_window": payload["backtest_window"],
                "analysis_input": {
                    "symbols": payload["symbols"],
                    "positions": payload["positions"],
                },
                "items": [
                    {
                        "symbol": "MSFT.US",
                        "quantity": 0.0,
                        "avg_cost": 0.0,
                        "mark_price": 0.0,
                        "unrealized_pnl": 0.0,
                        "unrealized_pnl_pct": 0.0,
                        "fill_summary": {"count": 0, "buy_quantity": 0.0, "sell_quantity": 0.0},
                        "shadow": {"action": "UNKNOWN", "confidence": 0, "reason": "未启用影子意见"},
                        "backtest": {
                            "status": "no_data",
                            "total_return": 0.0,
                            "max_drawdown": 0.0,
                            "trade_count": 0,
                            "score": "N/A",
                        },
                        "recommendation": {"action": "WATCH", "confidence": 0.4, "reason": "test"},
                        "analysis_context": {
                            "lot_count": 2,
                            "total_quantity": 3.0,
                            "total_cost": 1266.0,
                            "weighted_avg_cost": 422.0,
                            "first_buy_date": "2026-06-01T09:30:00+08:00",
                            "last_buy_date": "2026-06-03T09:30:00+08:00",
                        },
                    }
                ],
            }

    monkeypatch.setattr(routes_alpha, "AlphaPortfolioReportService", FakeReportService)
    client = authenticated_client

    response = client.post(
        "/api/v1/alpha/portfolio/report",
        json={
            "symbols": ["msft"],
            "positions": [
                {
                    "symbol": "msft",
                    "lots": [
                        {
                            "buy_date": "2026-06-01T09:30:00+08:00",
                            "buy_price": 420.0,
                            "quantity": 2.0,
                        },
                        {
                            "buy_date": "2026-06-03T09:30:00+08:00",
                            "buy_price": 426.0,
                            "quantity": 1.0,
                        },
                    ],
                }
            ],
            "include_shadow": False,
            "include_backtest": False,
            "backtest_window": "30d",
            "opening_cash": 10_000.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_input"] == {
        "symbols": ["MSFT.US"],
        "positions": [
            {
                "symbol": "MSFT.US",
                "lots": [
                    {
                        "buy_date": "2026-06-01T09:30:00+08:00",
                        "buy_price": 420.0,
                        "quantity": 2.0,
                    },
                    {
                        "buy_date": "2026-06-03T09:30:00+08:00",
                        "buy_price": 426.0,
                        "quantity": 1.0,
                    },
                ],
            }
        ],
    }
    assert body["items"][0]["symbol"] == "MSFT.US"
    assert body["items"][0]["analysis_context"] == {
        "lot_count": 2,
        "total_quantity": 3.0,
        "total_cost": 1266.0,
        "weighted_avg_cost": 422.0,
        "first_buy_date": "2026-06-01T09:30:00+08:00",
        "last_buy_date": "2026-06-03T09:30:00+08:00",
    }


def _authenticated_client(test_app):
    from src.core.config import Settings

    client = TestClient(test_app)
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": "reporter01",
            "email": "reporter01@example.com",
            "password": "TestPass123!",
        },
    )
    assert register.status_code in (200, 201, 409)
    login = client.post(
        "/api/v1/auth/login",
        json={"account": "reporter01", "password": "TestPass123!"},
    )
    assert login.status_code == 200
    cookie_name = Settings().auth_cookie_name
    assert cookie_name in client.cookies
    return client


def test_alpha_submit_returns_409_when_capability_disabled(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeExecutionService:
        def get_capability(self):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

        def build_submission(self, request):
            return {"mode": "manual", "enabled": False, "reason": "manual execution only"}

    monkeypatch.setattr(routes_alpha, "_get_alpha_execution_service", lambda: FakeExecutionService())

    app = build_app()
    client = authenticated_client

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
