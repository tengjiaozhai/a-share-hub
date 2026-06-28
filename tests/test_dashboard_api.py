from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

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
    decision_run_id = store.insert_decision_run(symbol="600519.SH",
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
    target_position_id = store.insert_target_position(decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        target_position_ratio=0.1,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = store.insert_execution_order(target_position_id=target_position_id,
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

def ensure_paper_ledger_tables(engine) -> None:
    from src.paper_ledger.models import PaperBase

    PaperBase.metadata.create_all(engine)

def test_dashboard_workbench_route_exists(authenticated_client, test_app):
    client = authenticated_client
    response = client.get("/api/v1/dashboard/workbench")
    assert response.status_code == 200

def test_workbench_payload_has_stable_contract(authenticated_client, test_app, pg_store):
    decision_run_id, target_position_id, execution_order_id = seed_dashboard_records(pg_store)
    client = authenticated_client

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

def test_kill_switch_events_are_visible_in_workbench_history(authenticated_client, test_app):
    client = authenticated_client

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

def test_workbench_payload_includes_alpha_panel(authenticated_client, test_app, pg_store):
    client = authenticated_client

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert "alpha" in payload
    assert "portfolio" in payload["alpha"]

def test_workbench_payload_includes_alpha_portfolio(authenticated_client, test_app, pg_store):
    pg_store.insert_alpha_holdings_entry(
        symbol="AAPLx",
        buy_date="2026-06-01",
        buy_price=201.0,
        quantity=1.2,
    )
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

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert payload["alpha"]["portfolio"]["snapshot"]["nav"] == 8_798.8
    assert payload["alpha"]["portfolio"]["fills"][0]["asset_symbol"] == "AAPLx"

def test_workbench_uses_authoritative_target_quantity_and_reconcile_items(authenticated_client, test_app, pg_store):
    pg_store.upsert_dashboard_run_summary(run_context_id="wrk-001",
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

    client = authenticated_client
    response = client.get("/api/v1/dashboard/workbench?run_context_id=wrk-001")
    payload = response.json()

    assert response.status_code == 200
    assert payload["latest_run"]["target_items"][0]["target_quantity"] == 4
    assert payload["latest_run"]["reconcile_items"][0]["mark_price"] == 99.90
    assert payload["latest_run"]["run_pnl_summary"]["net_pnl"] == -0.96

def test_history_returns_single_canonical_runs_list(authenticated_client, test_app, pg_store):
    from src.core.tenant import TenantContext
    from src.paper_ledger.store import PaperLedgerStore

    ensure_paper_ledger_tables(pg_store.engine)
    with Session(pg_store.engine) as session:
        ledger = PaperLedgerStore(session, TenantContext("test-user"))
        account = ledger.get_or_create_account(market="a", account_kind="auto")
        auto_run = ledger.create_run(
            account_id=account.account_id,
            market="a",
            trade_date=date(2026, 6, 16),
            run_source="auto",
            params={"strategy": "shadow"},
            watchlist=["600519.SH", "000858.SZ"],
        )
        ledger.update_run_status(auto_run.run_id, "success")
        auto_run_id = auto_run.run_id

    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-history-001",
        trade_date="2026-06-17",
        decision_mode="real",
        execution_mode="full",
        capital_base=1_000_000,
        status="completed",
        execution_fee_total=12.5,
        realized_pnl=100.0,
        unrealized_pnl=-25.5,
        net_pnl=74.5,
        started_at="2026-06-17T09:30:00+08:00",
        finished_at="2026-06-17T09:35:00+08:00",
        latest_workbench={
            "latest_run": {
                "run_context_id": "wrk-history-001",
                "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
                "decision_items": [{"symbol": "600519.SH"}, {"symbol": "000858.SZ"}],
                "target_items": [{"symbol": "600519.SH"}],
                "order_items": [{"symbol": "600519.SH"}],
                "run_pnl_summary": {"net_pnl": 74.5},
                "error_message": None,
            }
        },
    )

    client = authenticated_client
    response = client.get("/api/v1/dashboard/history?limit=10")
    payload = response.json()

    assert response.status_code == 200
    assert set(payload.keys()) == {"runs", "cursor", "has_more", "next_cursor", "total_count", "manual_count", "auto_count"}
    assert "auto_runs" not in payload
    assert "manual_runs" not in payload
    assert payload["cursor"] is None
    assert payload["has_more"] is False
    assert payload["next_cursor"] is None
    assert payload["total_count"] == 2
    assert payload["manual_count"] == 1
    assert payload["auto_count"] == 1

    runs = payload["runs"]
    assert len(runs) == 2

    manual_run = next(run for run in runs if run["source"] == "manual")
    assert manual_run == {
        "id": "wrk-history-001",
        "source": "manual",
        "market": "a",
        "status": "completed",
        "trade_date": "2026-06-17",
        "created_at": "2026-06-17T09:30:00+08:00",
        "finished_at": "2026-06-17T09:35:00+08:00",
        "decision_mode": "real",
        "execution_mode": "full",
        "watchlist_count": 3,
        "decision_count": 2,
        "target_count": 1,
        "order_count": 1,
        "net_pnl": 74.5,
        "error_message": None,
        "run_context_id": "wrk-history-001",
        "supports_case_view": True,
    }

    auto_history_run = next(run for run in runs if run["source"] == "auto")
    assert auto_history_run["id"] == auto_run_id
    assert auto_history_run["market"] == "a"
    assert auto_history_run["status"] == "success"
    assert auto_history_run["trade_date"] == "2026-06-16"
    assert auto_history_run["created_at"] is not None
    assert auto_history_run["finished_at"] is None
    assert auto_history_run["decision_mode"] is None
    assert auto_history_run["execution_mode"] is None
    assert auto_history_run["watchlist_count"] == 2
    assert auto_history_run["decision_count"] is None
    assert auto_history_run["target_count"] is None
    assert auto_history_run["order_count"] is None
    assert auto_history_run["net_pnl"] is None
    assert auto_history_run["error_message"] is None
    assert auto_history_run["run_context_id"] is None
    assert auto_history_run["supports_case_view"] is False

def test_history_manual_runs_link_case_view_by_run_context_id(authenticated_client, test_app, pg_store):
    ensure_paper_ledger_tables(pg_store.engine)
    pg_store.upsert_dashboard_run_summary(run_context_id="wrk-history-404",
        trade_date="2026-06-18",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=500_000,
        status="failed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at="2026-06-18T10:00:00+08:00",
        finished_at="2026-06-18T10:01:00+08:00",
        latest_workbench={
            "market": "a",
            "latest_run": {
                "run_context_id": "wrk-history-404",
                "watchlist": [],
                "decision_items": [],
                "target_items": [],
                "order_items": [],
                "error_message": "upstream unavailable",
            }
        },
    )

    client = authenticated_client
    history_payload = client.get("/api/v1/dashboard/history?limit=10").json()
    manual_run = next(run for run in history_payload["runs"] if run["id"] == "wrk-history-404")

    assert manual_run["supports_case_view"] is True
    assert manual_run["run_context_id"] == "wrk-history-404"

    workbench_response = client.get("/api/v1/dashboard/workbench?run_context_id=wrk-history-404")
    assert workbench_response.status_code == 200
    assert workbench_response.json()["latest_run"]["run_context_id"] == "wrk-history-404"

def test_history_supports_cursor_pagination_for_incremental_loading(authenticated_client, test_app, pg_store):
    ensure_paper_ledger_tables(pg_store.engine)
    pg_store.upsert_dashboard_run_summary(run_context_id="wrk-history-101",
        trade_date="2026-06-18",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=500_000,
        status="completed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=1.0,
        started_at="2026-06-18T10:02:00+08:00",
        finished_at="2026-06-18T10:03:00+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-history-101", "watchlist": ["NVDA"]}},
        market="us",
    )
    pg_store.upsert_dashboard_run_summary(run_context_id="wrk-history-102",
        trade_date="2026-06-18",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=500_000,
        status="completed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=2.0,
        started_at="2026-06-18T10:04:00+08:00",
        finished_at="2026-06-18T10:05:00+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-history-102", "watchlist": ["AAPL"]}},
        market="us",
    )
    pg_store.upsert_dashboard_run_summary(run_context_id="wrk-history-103",
        trade_date="2026-06-18",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=500_000,
        status="completed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=3.0,
        started_at="2026-06-18T10:06:00+08:00",
        finished_at="2026-06-18T10:07:00+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-history-103", "watchlist": ["MSFT"]}},
        market="us",
    )

    client = authenticated_client

    first_page = client.get("/api/v1/dashboard/history?market=us&source=manual&limit=2")
    assert first_page.status_code == 200
    first_payload = first_page.json()

    assert [run["id"] for run in first_payload["runs"]] == ["wrk-history-103", "wrk-history-102"]
    assert first_payload["has_more"] is True
    assert first_payload["cursor"] is None
    assert first_payload["next_cursor"]

    second_page = client.get(
        f"/api/v1/dashboard/history?market=us&source=manual&limit=2&cursor={first_payload['next_cursor']}"
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()

    assert [run["id"] for run in second_payload["runs"]] == ["wrk-history-101"]
    assert second_payload["has_more"] is False
    assert second_payload["cursor"] == first_payload["next_cursor"]
    assert second_payload["next_cursor"] is None

def test_history_filters_manual_runs_by_persisted_run_market_not_request_fallback(authenticated_client, test_app, pg_store):
    ensure_paper_ledger_tables(pg_store.engine)
    pg_store.insert_decision_run(
        symbol="AAPL",
        prompt_hash="wrk-history-us",
        run_context_id="wrk-history-us",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.1,
        reason="seed us run",
        input_snapshot={
            "features": {"watchlist": ["AAPL"]},
            "market_context": {"market": "us"},
        },
    )
    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-history-us",
        trade_date="2026-06-18",
        decision_mode="mock",
        execution_mode="decision",
        capital_base=500_000,
        status="completed",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=3.0,
        started_at="2026-06-18T10:06:00+08:00",
        finished_at="2026-06-18T10:07:00+08:00",
        latest_workbench={"latest_run": {"run_context_id": "wrk-history-us", "watchlist": []}},
    )

    client = authenticated_client

    a_market_payload = client.get("/api/v1/dashboard/history?market=a&source=manual&limit=10").json()
    us_market_payload = client.get("/api/v1/dashboard/history?market=us&source=manual&limit=10").json()

    assert "wrk-history-us" not in [run["id"] for run in a_market_payload["runs"]]
    assert "wrk-history-us" in [run["id"] for run in us_market_payload["runs"]]

def test_performance_includes_window_metadata_and_comparison_cards(authenticated_client, test_app, pg_store):
    from src.core.tenant import TenantContext
    from src.paper_ledger.store import PaperLedgerStore

    account_kind = "perf-meta-case"
    ensure_paper_ledger_tables(pg_store.engine)
    with Session(pg_store.engine) as session:
        ledger = PaperLedgerStore(session, TenantContext("test-user"))
        account = ledger.get_or_create_account(market="a", account_kind=account_kind)
        ledger.create_nav_snapshot(
            account_id=account.account_id,
            trade_date=date(2026, 6, 16),
            nav=100.0,
            cash=100.0,
            positions_value=0.0,
        )
        ledger.create_nav_snapshot(
            account_id=account.account_id,
            trade_date=date(2026, 6, 17),
            nav=103.0,
            cash=103.0,
            positions_value=0.0,
        )
        ledger.create_nav_snapshot(
            account_id=account.account_id,
            trade_date=date(2026, 6, 18),
            nav=108.0,
            cash=108.0,
            positions_value=0.0,
        )

    client = authenticated_client
    response = client.get(f"/api/v1/dashboard/performance?window=30d&account_kind={account_kind}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["window"] == "30d"
    assert payload["start_date"] == "2026-06-16"
    assert payload["end_date"] == "2026-06-18"
    assert payload["sample_count"] == 3
    assert payload["window_return"] == 0.08
    assert isinstance(payload["comparison_cards"], list)
    assert {card["window"] for card in payload["comparison_cards"]} == {"7d", "30d", "90d", "ytd"}

def test_old_run_endpoint_is_removed(authenticated_client, test_app, monkeypatch):
    """旧阻塞式 /api/v1/dashboard/run 必须删除（No Legacy By Default）。

    ShadowRunService.run() + POST /api/v1/dashboard/runs 是统一权威入口。
    """
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config, user_id=None: None)

    client = authenticated_client
    res = client.post(
        "/api/v1/dashboard/run",
        json={"watchlist": ["NVDA"], "capital_base": 1_000_000},
    )
    assert res.status_code == 404, (
        f"legacy /api/v1/dashboard/run must be gone, got {res.status_code}: {res.text}"
    )

def test_new_runs_endpoint_remains(authenticated_client, test_app, monkeypatch):
    """新流式 endpoint /api/v1/dashboard/runs 必须保留为唯一入口。"""
    from src.api import routes_dashboard

    monkeypatch.setattr(routes_dashboard, "_launch_dashboard_run", lambda run_context_id, config, user_id=None: None)

    client = authenticated_client
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
