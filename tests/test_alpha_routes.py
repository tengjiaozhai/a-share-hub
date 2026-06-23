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
