from datetime import datetime, timedelta

from fastapi.testclient import TestClient


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


def test_run_endpoint_returns_full_workbench_payload(test_app):
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
