from datetime import datetime, timedelta

from fastapi.testclient import TestClient


class FakeLLM:
    model = "deepseek-v4-pro"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        symbol = "600519.SH"
        if "000858.SZ" in prompt:
            symbol = "000858.SZ"
        elif "601318.SH" in prompt:
            symbol = "601318.SH"
        return (
            f'{{"symbol":"{symbol}","action":"BUY","confidence":80,'
            f'"target_position_ratio":0.1,"reason":"real-mode"}}'
        )


def seed_dashboard_records(store):
    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="hash-001",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="dashboard seed",
        input_snapshot={
            "symbol": "600519.SH",
            "features": {"capital_base": 1000000, "watchlist": ["600519.SH"]},
            "market_context": {"mode": "shadow"},
        },
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        target_position_ratio=0.1,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1000.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "paper-001"},
    )
    return decision_run_id, target_position_id, execution_order_id


def test_dashboard_workbench_route_exists(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/dashboard/workbench")
    assert response.status_code == 200


def test_workbench_payload_has_stable_contract(test_app, pg_store):
    decision_run_id, target_position_id, execution_order_id = seed_dashboard_records(pg_store)
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")
    payload = response.json()

    assert response.status_code == 200
    required_top_level = {
        "mode",
        "trade_date",
        "last_run_at",
        "services",
        "kill_switch",
        "risk",
        "latest_run",
        "history",
    }
    assert required_top_level.issubset(payload.keys())

    required_history = {"decisions", "orders", "targets", "events"}
    assert required_history.issubset(payload["history"].keys())

    decision = payload["history"]["decisions"][0]
    assert decision["decision_run_id"] == decision_run_id
    assert decision["action"] == "BUY"
    assert decision["parsed_action"] == "BUY"

    target = payload["history"]["targets"][0]
    assert target["target_position_id"] == target_position_id

    order = payload["history"]["orders"][0]
    assert order["execution_order_id"] == execution_order_id
    assert {"symbol", "action", "quantity", "limit_price", "status", "created_at"}.issubset(order.keys())


def test_run_endpoint_returns_full_workbench_payload(test_app, monkeypatch):
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_get_llm", lambda: FakeLLM())

    client = TestClient(test_app)

    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert {"mode", "trade_date", "last_run_at", "services", "kill_switch", "risk", "latest_run", "history"}.issubset(
        payload.keys()
    )
    assert len(payload["history"]["decisions"]) >= 1
    assert len(payload["history"]["targets"]) >= 1
    assert len(payload["history"]["orders"]) >= 1
    assert {"symbol", "action", "quantity", "limit_price", "status", "created_at"}.issubset(
        payload["history"]["orders"][0].keys()
    )
    assert payload["history"]["decisions"][0]["action"] in {"BUY", "SELL", "HOLD"}


def test_workbench_refresh_preserves_real_decision_mode(test_app, monkeypatch):
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_get_llm", lambda: FakeLLM())

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "real",
        },
    )
    assert response.status_code == 200

    refresh = client.get("/api/v1/dashboard/workbench")
    payload = refresh.json()
    assert refresh.status_code == 200
    assert "模式: real" in payload["latest_run"]["steps"][0]["message"]


def test_run_endpoint_contains_reconcile_stage_and_daily_pnl(test_app):
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert "daily_pnl" in payload["risk"]
    assert isinstance(payload["risk"]["daily_pnl"], (int, float))

    steps = payload["latest_run"]["steps"]
    assert len(steps) >= 8
    assert [step["stage"] for step in steps[-2:]] == ["reconcile", "reconcile"]
    assert [step["status"] for step in steps[-2:]] == ["running", "done"]
    assert "模拟盈亏" in (steps[-1].get("message") or "")


def test_decision_mode_marks_reconcile_as_skipped(test_app):
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "decision",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    steps = payload["latest_run"]["steps"]
    assert steps[-1]["stage"] == "reconcile"
    assert steps[-1]["status"] == "done"
    assert "仅决策模式，跳过执行" in (steps[-1].get("message") or "")


def test_kill_switch_events_are_visible_in_workbench_history(test_app):
    client = TestClient(test_app)

    activate = client.post("/api/v1/kill-switch/activate", json={"reason": "dashboard manual halt"})
    assert activate.status_code == 200
    assert activate.json()["reason"] == "dashboard manual halt"

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["kill_switch"]["active"] is True
    assert any(
        event["type"] == "kill_switch_event" and event["active"] is True and event["reason"] == "dashboard manual halt"
        for event in payload["history"]["events"]
    )

    deactivate = client.post("/api/v1/kill-switch/deactivate", json={"reason": "dashboard manual resume"})
    assert deactivate.status_code == 200
    assert deactivate.json()["reason"] == "dashboard manual resume"

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["kill_switch"]["active"] is False
    assert any(
        event["type"] == "kill_switch_event" and event["active"] is False and event["reason"] == "dashboard manual resume"
        for event in payload["history"]["events"]
    )


def test_workbench_payload_includes_alpha_panel(test_app, pg_store):
    ticket_id = pg_store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="discount to reference",
        suggested_quantity=2.0,
        suggested_limit_price=210.5,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert "alpha" in payload
    assert payload["alpha"]["tickets"][0]["ticket_id"] == ticket_id


def test_workbench_payload_includes_alpha_portfolio_and_exceptions(test_app, pg_store):
    pg_store.replace_alpha_positions(
        [{"symbol": "AAPLx", "quantity": 1.2, "avg_cost": 201.0, "mark_price": 225.0}]
    )
    pg_store.insert_alpha_portfolio_snapshot(
        cash_balance=8_500.0,
        realized_pnl=20.0,
        unrealized_pnl=28.8,
        nav=8_798.8,
    )
    pg_store.insert_alpha_reconciliation_run(
        source="manual",
        status="MISMATCH",
        discrepancies={"positions": {"AAPLx": {"internal": 1.2, "external": 1.0}}},
    )
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert payload["alpha"]["portfolio"]["snapshot"]["nav"] == 8_798.8
    assert payload["alpha"]["exceptions"]["latest_status"] == "MISMATCH"


def test_run_endpoint_uses_watchlist_allocation_for_order_quantity(test_app, monkeypatch):
    from src.api import routes_dashboard

    class FakeSnap:
        close = 100.0

    def fake_quote(self, symbol):
        return FakeSnap()

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", fake_quote)
    monkeypatch.setattr(routes_dashboard, "_get_llm", lambda: FakeLLM())

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "watchlist": ["600519.SH", "000001.SZ"],
            "capital_base": 1_000_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    buy_orders = [
        item for item in payload["latest_run"]["order_items"]
        if item["action"] == "BUY"
    ]
    assert buy_orders[0]["quantity"] == 1000
