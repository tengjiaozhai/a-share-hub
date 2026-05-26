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


def test_workbench_payload_uses_runtime_store_metrics(test_app, pg_store):
    decision_run_id, target_position_id, execution_order_id = seed_dashboard_records(pg_store)
    client = TestClient(test_app)

    response = client.get("/api/v1/dashboard/workbench")
    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"] == {
        "active_target_count": 1,
        "active_target_value": 100000,
        "open_orders": 1,
        "recent_decisions": 1,
    }
    assert payload["history"]["decisions"][0]["decision_run_id"] == decision_run_id
    assert payload["history"]["targets"][0]["target_position_id"] == target_position_id
    assert payload["history"]["orders"][0]["execution_order_id"] == execution_order_id
    assert "daily_pnl" not in payload["summary"]


def test_kill_switch_activate_records_event_and_updates_workbench(test_app):
    client = TestClient(test_app)

    activate = client.post("/api/v1/kill-switch/activate", json={"reason": "dashboard manual halt"})
    assert activate.status_code == 200

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["risk"]["kill_switch_active"] is True
    assert payload["history"]["kill_switch_events"][0]["reason"] == "dashboard manual halt"


def test_kill_switch_deactivate_records_resume_event(test_app):
    client = TestClient(test_app)
    client.post("/api/v1/kill-switch/activate", json={"reason": "dashboard manual halt"})

    deactivate = client.post("/api/v1/kill-switch/deactivate", json={"reason": "dashboard manual resume"})
    assert deactivate.status_code == 200

    payload = client.get("/api/v1/dashboard/workbench").json()
    assert payload["risk"]["kill_switch_active"] is False
    assert payload["history"]["kill_switch_events"][0]["reason"] == "dashboard manual resume"


def test_workbench_reflects_latest_simulation_run(test_app):
    client = TestClient(test_app)

    response = client.post(
        "/api/v1/dashboard/simulations",
        json={
            "capital_base": 1000000,
            "watchlist": ["600519.SH"],
            "manual_symbols": "300750.SZ",
            "max_position_ratio": 0.2,
            "stop_loss_ratio": 0.03,
            "daily_loss_limit_ratio": 0.05,
            "execution_mode": "full_cycle",
        },
    )
    assert response.status_code == 200

    workbench = client.get("/api/v1/dashboard/workbench").json()
    assert workbench["summary"]["recent_decisions"] >= 1
    assert len(workbench["history"]["decisions"]) >= 1
    assert len(workbench["history"]["orders"]) >= 1
    assert workbench["risk"]["healthy"] is True
