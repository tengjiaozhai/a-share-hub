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


def test_workbench_uses_authoritative_target_quantity_and_reconcile_items(test_app, pg_store):
    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-001",
        trade_date="2026-06-15",
        decision_mode="real",
        execution_mode="full",
        capital_base=10_000,
        status="completed",
        execution_fee_total=0.36,
        realized_pnl=0.0,
        unrealized_pnl=-0.60,
        net_pnl=-0.96,
        started_at="2026-06-15T20:15:06+08:00",
        finished_at="2026-06-15T20:15:38+08:00",
        latest_workbench={
            "latest_run": {
                "run_context_id": "wrk-001",
                "target_items": [{"symbol": "NVDA", "target_quantity": 4}],
                "reconcile_items": [{"symbol": "NVDA", "mark_price": 99.90}],
                "run_pnl_summary": {"net_pnl": -0.96},
            }
        },
    )

    client = TestClient(test_app)
    response = client.get("/api/v1/dashboard/workbench?run_context_id=wrk-001")
    payload = response.json()

    assert response.status_code == 200
    assert payload["latest_run"]["target_items"][0]["target_quantity"] == 4
    assert payload["latest_run"]["reconcile_items"][0]["mark_price"] == 99.90
    assert payload["latest_run"]["run_pnl_summary"]["net_pnl"] == -0.96


def test_old_run_endpoint_is_removed(test_app, monkeypatch):
    """旧阻塞式 /api/v1/dashboard/run 必须删除（No Legacy By Default）。

    ShadowRunService.run() + POST /api/v1/dashboard/runs 是统一权威入口。
    """
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config: None)

    client = TestClient(test_app)
    res = client.post(
        "/api/v1/dashboard/run",
        json={"watchlist": ["NVDA"], "capital_base": 1_000_000},
    )
    assert res.status_code == 404, (
        f"legacy /api/v1/dashboard/run must be gone, got {res.status_code}: {res.text}"
    )


def test_new_runs_endpoint_remains(test_app, monkeypatch):
    """新流式 endpoint /api/v1/dashboard/runs 必须保留为唯一入口。"""
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config: None)

    client = TestClient(test_app)
    res = client.post(
        "/api/v1/dashboard/runs",
        json={
            "watchlist": ["NVDA"],
            "capital_base": 1_000_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "mock",
        },
    )
    assert res.status_code == 202, f"new /api/v1/dashboard/runs must remain, got {res.status_code}: {res.text}"
    body = res.json()
    assert body["run_context_id"].startswith("wrk-")
    assert body["stream_url"] == f"/api/v1/dashboard/runs/{body['run_context_id']}/events"
