import pandas as pd

from src.api import routes_alpha


def test_old_portfolio_report_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report", json={"symbols": ["MU.US"]}
    )
    assert response.status_code == 404


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
    assert created["market"] == "us"
    assert created["buy_date"] == "2026-06-20"
    assert created["buy_price"] == 420.5
    assert created["quantity"] == 2.0

    list_resp = client.get("/api/v1/alpha/holdings")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert len(listed["items"]) == 1
    assert listed["markets"]["us"][0]["symbol"] == "MSFT.US"

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


def test_alpha_holdings_accepts_verified_fund_code_without_exchange_suffix(authenticated_client, test_app, pg_store):
    routes_alpha._rebuild_holdings_portfolio = lambda store: None

    response = authenticated_client.post(
        "/api/v1/alpha/holdings",
        json={
            "symbol": "512650",
            "buy_date": "2026-06-20",
            "buy_price": 1.2345,
            "quantity": 1000.0,
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["symbol"] == "512650.SH"
    assert created["market"] == "fund"
    assert created["buy_price"] == 1.2345
    assert created["quantity"] == 1000.0


def test_alpha_holdings_groups_markets_in_backend(authenticated_client, test_app, pg_store):
    routes_alpha._rebuild_holdings_portfolio = lambda store: None
    for symbol in ("600519.SH", "MSFT.US", "020972.OTC"):
        response = authenticated_client.post(
            "/api/v1/alpha/holdings",
            json={
                "symbol": symbol,
                "buy_date": "2026-06-20",
                "buy_price": 10.0,
                "quantity": 1.0,
            },
        )
        assert response.status_code == 200

    data = authenticated_client.get("/api/v1/alpha/holdings").json()

    assert [item["symbol"] for item in data["markets"]["a"]] == ["600519.SH"]
    assert [item["symbol"] for item in data["markets"]["us"]] == ["MSFT.US"]
    assert [item["symbol"] for item in data["markets"]["fund"]] == ["020972.OTC"]

    fund_only = authenticated_client.get("/api/v1/alpha/holdings", params={"market": "fund"}).json()
    assert [item["symbol"] for item in fund_only["items"]] == ["020972.OTC"]


def test_backtest_runner_uses_current_akshare_provider(monkeypatch):
    class FakeAkshareProvider:
        def get_history(self, symbol, start_date, end_date):
            rows = []
            for day in range(61):
                rows.append(
                    {
                        "date": f"2026-01-{day + 1:02d}",
                        "open": 10.0 + day,
                        "high": 11.0 + day,
                        "low": 9.0 + day,
                        "close": 10.5 + day,
                        "volume": 1000 + day,
                    }
                )
            return pd.DataFrame(rows)

    monkeypatch.setattr(
        "src.data.providers.akshare_provider.AkshareProvider",
        FakeAkshareProvider,
    )
    monkeypatch.setattr(
        "src.backtest.engine.run_daily_backtest",
        lambda **kwargs: {
            "final_nav": 1_050_000,
            "equity_curve": [{"date": "2026-01-01", "equity": 1_000_000}],
            "trades": [],
        },
    )
    monkeypatch.setattr(
        "src.backtest.metrics.calculate_metrics",
        lambda equity_curve, trades: {
            "total_return": 0.05,
            "annualized_return": 0.05,
            "max_drawdown": 0.01,
            "sharpe_ratio": 1.2,
            "win_rate": 0.0,
        },
    )

    runner = routes_alpha._build_backtest_runner(engine=None, tenant=None, user_id="u1")
    snapshot = type("Snapshot", (), {"symbol": "600703.SH", "market": "a", "technical": {}})()

    result = runner(snapshot)

    assert result["status"] == "completed"
    assert result["symbol"] == "600703.SH"
    assert result["final_nav"] == 1_050_000
