def test_start_run_returns_accepted_and_run_context_id(test_app, authenticated_client, monkeypatch):
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config, user_id: None)

    response = authenticated_client.post(
        "/api/v1/dashboard/runs",
        json={
            "watchlist": ["NVDA", "AAPL"],
            "capital_base": 10_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "real",
        },
    )

    payload = response.json()
    assert response.status_code == 202
    assert payload["run_context_id"].startswith("wrk-")
    assert payload["stream_url"] == f"/api/v1/dashboard/runs/{payload['run_context_id']}/events"


def test_run_events_route_streams_ordered_event_log(authenticated_client, pg_store):
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "accepted"},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-001",
        event_type="run.completed",
        stage="reconcile",
        status="done",
        payload={"message": "completed"},
    )
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
        latest_workbench={"latest_run": {"run_context_id": "wrk-001"}},
    )

    with authenticated_client.stream("GET", "/api/v1/dashboard/runs/wrk-001/events") as response:
        body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert 'event: run.accepted' in body
    assert 'event: run.completed' in body
    assert '"run_context_id": "wrk-001"' in body
