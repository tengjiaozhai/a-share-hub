from src.api import routes_alpha


def test_generate_portfolio_report_endpoint(authenticated_client, test_app, monkeypatch):
    class FakeReportService:
        def generate_report(self, payload):
            return {
                "generated_at": "2026-06-22T15:10:00+08:00",
                "backtest_window": payload["backtest_window"],
                "analysis_input": {"symbols": payload["symbols"], "positions": payload["positions"]},
                "items": [
                    {
                        "run_id": "alpha-analysis-test",
                        "status": "completed",
                        "snapshot": {"symbol": "AAPLx", "close": 210.0},
                        "research": {"rating": "OVERWEIGHT"},
                        "trader": {"action": "BUY"},
                        "risk": {"action": "ADD"},
                        "model_name": "deepseek-v4-pro",
                        "error": None,
                    }
                ],
            }

    monkeypatch.setattr(routes_alpha, "_build_report_service", lambda store: FakeReportService())
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
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert "shadow" not in item
    assert "recommendation" not in item
    assert item["risk"]["action"] in {"ADD", "HOLD", "REDUCE", "EXIT"}


def test_generate_portfolio_report_endpoint_normalizes_symbols_before_service(
    authenticated_client,
    test_app,
    monkeypatch,
):
    captured_payload = {}

    class FakeReportService:
        def generate_report(self, payload):
            captured_payload.update(payload)
            return {
                "generated_at": "2026-06-20T12:00:00+08:00",
                "backtest_window": payload["backtest_window"],
                "analysis_input": {
                    "symbols": payload["symbols"],
                    "positions": payload["positions"],
                },
                "items": [],
            }

    monkeypatch.setattr(routes_alpha, "_build_report_service", lambda store: FakeReportService())
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
        def generate_report(self, payload):
            return {
                "generated_at": "2026-06-20T12:00:00+08:00",
                "backtest_window": payload["backtest_window"],
                "analysis_input": {
                    "symbols": payload["symbols"],
                    "positions": payload["positions"],
                },
                "items": [
                    {
                        "run_id": "alpha-analysis-test",
                        "status": "completed",
                        "snapshot": {"symbol": "MSFT.US", "close": 420.0},
                        "research": {"rating": "OVERWEIGHT"},
                        "trader": {"action": "BUY"},
                        "risk": {"action": "ADD"},
                        "model_name": "deepseek-v4-pro",
                        "error": None,
                    }
                ],
            }

    monkeypatch.setattr(routes_alpha, "_build_report_service", lambda store: FakeReportService())
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
    item = body["items"][0]
    assert "shadow" not in item
    assert "recommendation" not in item
    assert item["risk"]["action"] in {"ADD", "HOLD", "REDUCE", "EXIT"}


def test_report_endpoint_removes_shadow_and_returns_final_risk(authenticated_client, monkeypatch):
    class FakeReportService:
        def generate_report(self, payload):
            return {
                "generated_at": "2026-06-22T15:10:00+08:00",
                "backtest_window": payload["backtest_window"],
                "analysis_input": {"symbols": payload["symbols"], "positions": payload["positions"]},
                "items": [
                    {
                        "run_id": "alpha-analysis-test",
                        "status": "completed",
                        "snapshot": {"symbol": "600703.SH", "close": 16.0},
                        "research": {"rating": "OVERWEIGHT"},
                        "trader": {"action": "BUY"},
                        "risk": {"action": "ADD"},
                        "model_name": "deepseek-v4-pro",
                        "error": None,
                    }
                ],
            }

    monkeypatch.setattr(routes_alpha, "_build_report_service", lambda store: FakeReportService())
    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report",
        json={"symbols": ["600703"], "backtest_window": "60d"},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "shadow" not in item
    assert "recommendation" not in item
    assert item["risk"]["action"] in {"ADD", "HOLD", "REDUCE", "EXIT"}


def test_analysis_history_is_user_scoped(authenticated_client, pg_store):
    response = authenticated_client.get(
        "/api/v1/alpha/analysis-runs",
        params={"symbol": "600703.SH", "limit": 10},
    )
    assert response.status_code == 200
    assert "items" in response.json()


def test_alpha_holdings_crud_endpoints(authenticated_client, test_app, pg_store):
    routes_alpha._rebuild_holdings_portfolio = lambda store: None
    client = authenticated_client

    create_resp = client.post(
        "/api/v1/alpha/holdings",
        json={
            "symbol": "msft",
            "buy_date": "2026-06-20",
            "buy_price": 420.5,
            "quantity": 2.0,
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["symbol"] == "MSFT.US"
    assert created["buy_date"] == "2026-06-20"
    assert created["buy_price"] == 420.5
    assert created["quantity"] == 2.0

    list_resp = client.get("/api/v1/alpha/holdings")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    entry_id = created["entry_id"]
    update_resp = client.put(
        f"/api/v1/alpha/holdings/{entry_id}",
        json={
            "symbol": "msft",
            "buy_date": "2026-06-21",
            "buy_price": 425.0,
            "quantity": 3.0,
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["buy_date"] == "2026-06-21"
    assert updated["buy_price"] == 425.0
    assert updated["quantity"] == 3.0

    delete_resp = client.delete(f"/api/v1/alpha/holdings/{entry_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"ok": True}
    assert client.get("/api/v1/alpha/holdings").json()["items"] == []
