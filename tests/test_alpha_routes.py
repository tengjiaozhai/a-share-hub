from src.alpha.portfolio_service import AlphaPortfolioService
from src.api import routes_alpha


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
