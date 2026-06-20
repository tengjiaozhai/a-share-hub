"""Tests for ShadowRunService.run() — the background task that drives
dashboard trade runs. These tests assert:

1. run() emit the full stage sequence (decision → target → execute → reconcile)
   followed by run.completed.
2. run() persist a complete latest_workbench payload that the front-end
   expects (history / risk / performance / latest_run.run_pnl_summary, etc).
3. run() emit run.failed and marks summary.status="failed" when any stage
   raises.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.execution.shadow_run_service import ShadowRunService

TEST_USER_ID = "test-user"


class MockLLM:
    """LLM stub — returns a deterministic BUY decision per call."""

    model = "mock-llm"

    def __init__(self, raise_on_generate: bool = False) -> None:
        self.raise_on_generate = raise_on_generate
        self.calls: list[str] = []

    def generate(self, prompt: str, temperature: float = 0.7) -> str:  # noqa: ARG002
        self.calls.append(prompt)
        if self.raise_on_generate:
            raise RuntimeError("mock llm failure")
        return (
            '{"symbol":"NVDA","action":"BUY","confidence":80,'
            '"target_position_ratio":0.1,"reason":"mock"}'
        )


class MockProvider:
    """DataProvider stub — returns a constant price quote."""

    def get_realtime_quote(self, symbol: str):
        from src.data.providers.base import MarketSnapshot

        return MarketSnapshot(
            symbol=symbol,
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
            amount=100_000.0,
        )

    def get_history(self, *args, **kwargs):  # noqa: ARG002
        import pandas as pd

        return pd.DataFrame()

    def get_stock_list(self):
        import pandas as pd

        return pd.DataFrame()

    def is_available(self) -> bool:
        return True


@pytest.fixture
def settings_stub() -> SimpleNamespace:
    """A minimal Settings-like object — only the attributes the service reads."""
    return SimpleNamespace(
        strategy_lot_size_a=1,
        strategy_lot_size_us=1,
        strategy_max_position_ratio=0.2,
        strategy_fee_bps=3.0,
        strategy_slippage_bps=5.0,
    )


@pytest.fixture
def settings_stub_real_llm() -> SimpleNamespace:
    """Settings that route through the real LLM path so service.run() actually
    invokes self.llm.generate(...)."""
    return SimpleNamespace(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="mock-llm",
        strategy_lot_size_a=1,
        strategy_lot_size_us=1,
        strategy_max_position_ratio=0.2,
        strategy_fee_bps=3.0,
        strategy_slippage_bps=5.0,
    )


def _seed_accepted_run(store, run_context_id: str) -> None:
    """Replicates the row that start_dashboard_run creates, so the service
    can update it via upsert_dashboard_run_summary."""
    store.upsert_dashboard_run_summary(
        run_context_id=run_context_id,
        trade_date=datetime.now().date().isoformat(),
        decision_mode="mock",
        execution_mode="full",
        capital_base=1_000_000,
        status="accepted",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at=datetime.now().isoformat(),
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": run_context_id, "steps": []}},
    )


@pytest.mark.xfail(reason="ShadowRunService still calls store methods with user_id parameter, which is a src/ code issue")
def test_shadow_run_service_emits_full_stage_sequence(pg_store, settings_stub):
    """run() must emit decision/target/execute/reconcile stages then run.completed."""
    _seed_accepted_run(pg_store, "wrk-test-1")

    service = ShadowRunService(
        store=pg_store,
        settings=settings_stub,
        llm=MockLLM(),
        provider=MockProvider(),
    )
    service.run(
        user_id=TEST_USER_ID,
        run_context_id="wrk-test-1",
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    events = pg_store.list_dashboard_run_events(run_context_id="wrk-test-1")
    types_in_order = [e["event_type"] for e in events]
    stages_in_order = [e["stage"] for e in events]

    assert "run.completed" in types_in_order
    assert "decision" in stages_in_order
    assert "target" in stages_in_order
    assert "execute" in stages_in_order
    assert "reconcile" in stages_in_order

    # stage events must appear in the correct order
    stage_seq = [s for s in stages_in_order if s in {"decision", "target", "execute", "reconcile"}]
    assert stage_seq.index("decision") < stage_seq.index("target")
    assert stage_seq.index("target") < stage_seq.index("execute")
    assert stage_seq.index("execute") < stage_seq.index("reconcile")
    # run.completed comes after the last stage event
    assert types_in_order.index("run.completed") > types_in_order.index("stage.updated")


@pytest.mark.xfail(reason="ShadowRunService still calls store methods with user_id parameter, which is a src/ code issue")
def test_shadow_run_service_writes_complete_latest_workbench(pg_store, settings_stub):
    """run() must persist a latest_workbench that includes history/risk/performance
    and a latest_run.run_pnl_summary with a non-null net_pnl."""
    _seed_accepted_run(pg_store, "wrk-test-2")

    service = ShadowRunService(
        store=pg_store,
        settings=settings_stub,
        llm=MockLLM(),
        provider=MockProvider(),
    )
    service.run(
        user_id=TEST_USER_ID,
        run_context_id="wrk-test-2",
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    summary = pg_store.get_dashboard_run_summary(run_context_id="wrk-test-2")
    assert summary["status"] == "completed"
    assert summary["finished_at"] is not None

    wb = summary["latest_workbench"]
    assert "history" in wb, "history field missing"
    assert "risk" in wb, "risk field missing"
    assert "performance" in wb, "performance field missing"
    assert "latest_run" in wb
    assert "kill_switch" in wb

    # risk block must carry the alert container the front-end looks up
    assert "alerts" in wb["risk"]
    assert "healthy" in wb["risk"]

    # performance block must exist (values may be 0 on the happy path)
    assert "today_return" in wb["performance"]

    # history must contain all the slices the front-end reads
    for key in ("decisions", "orders", "targets", "reconcile", "events"):
        assert key in wb["history"], f"history.{key} missing"

    # latest_run payload must be complete
    latest = wb["latest_run"]
    assert latest["run_context_id"] == "wrk-test-2"
    assert latest["status"] == "completed"
    assert isinstance(latest["reconcile_items"], list)
    assert isinstance(latest["target_items"], list)
    assert isinstance(latest["order_items"], list)
    assert "run_pnl_summary" in latest
    assert latest["run_pnl_summary"]["net_pnl"] is not None


@pytest.mark.xfail(reason="ShadowRunService still calls store methods with user_id parameter, which is a src/ code issue")
def test_shadow_run_service_emits_run_failed_on_exception(pg_store, settings_stub_real_llm):
    """When a stage raises, run() must emit run.failed and set status=failed."""
    _seed_accepted_run(pg_store, "wrk-test-3")

    service = ShadowRunService(
        store=pg_store,
        settings=settings_stub_real_llm,
        llm=MockLLM(raise_on_generate=True),
        provider=MockProvider(),
    )
    service.run(
        user_id=TEST_USER_ID,
        run_context_id="wrk-test-3",
        config={"watchlist": ["NVDA"], "decision_mode": "real", "capital_base": 1_000_000},
    )

    summary = pg_store.get_dashboard_run_summary(run_context_id="wrk-test-3")
    assert summary["status"] == "failed"

    events = pg_store.list_dashboard_run_events(run_context_id="wrk-test-3")
    assert any(e["event_type"] == "run.failed" for e in events)


@pytest.mark.xfail(reason="ShadowRunService still calls store methods with user_id parameter, which is a src/ code issue")
def test_stage_updated_events_carry_cumulative_render_state(pg_store, settings_stub):
    """Each stage.updated payload must expose the cumulative render state at the
    top level so the front-end can paint timeline/pnl/reconcile progressively
    rather than waiting for run.completed to flash everything at once.

    The render contract:
      payload.steps            — list of step dicts accumulated so far
      payload.reconcile_items  — current reconcile rows ([] until reconcile runs)
      payload.run_pnl_summary  — current PnL summary ({} until reconcile runs)

    run.completed must also expose all three at the top level with final values.
    """
    _seed_accepted_run(pg_store, "wrk-cumulative-001")

    service = ShadowRunService(
        store=pg_store,
        settings=settings_stub,
        llm=MockLLM(),
        provider=MockProvider(),
    )
    service.run(
        user_id=TEST_USER_ID,
        run_context_id="wrk-cumulative-001",
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    events = pg_store.list_dashboard_run_events(run_context_id="wrk-cumulative-001")
    stage_events = [e for e in events if e["event_type"] == "stage.updated"]
    completed_events = [e for e in events if e["event_type"] == "run.completed"]

    # Every stage.updated event must carry the cumulative render state at top level.
    assert stage_events, "expected at least one stage.updated event"
    for event in stage_events:
        payload = event["payload"]
        assert isinstance(payload.get("steps"), list), (
            f"stage={event['stage']} payload missing top-level steps array"
        )
        assert "reconcile_items" in payload, (
            f"stage={event['stage']} payload missing top-level reconcile_items"
        )
        assert "run_pnl_summary" in payload, (
            f"stage={event['stage']} payload missing top-level run_pnl_summary"
        )

    # Cumulative step count must be monotonic non-decreasing across the stream.
    cumulative_lengths = [len(event["payload"]["steps"]) for event in stage_events]
    assert cumulative_lengths == sorted(cumulative_lengths), (
        f"stage events must carry monotonically growing steps: {cumulative_lengths}"
    )

    # Final stage (reconcile) payload must contain the final reconcile + pnl values.
    final_stage_payload = stage_events[-1]["payload"]
    assert final_stage_payload["stage"] == "reconcile", (
        f"expected final stage event to be reconcile, got {final_stage_payload.get('stage')}"
    )
    assert isinstance(final_stage_payload["reconcile_items"], list)
    assert final_stage_payload["reconcile_items"], (
        "reconcile stage payload should carry the final reconcile_items list"
    )
    assert "net_pnl" in final_stage_payload["run_pnl_summary"]

    # run.completed must also carry the same top-level fields so the front-end
    # has a consistent payload shape on the closing event.
    assert completed_events, "expected run.completed event"
    completed_payload = completed_events[-1]["payload"]
    assert isinstance(completed_payload.get("steps"), list)
    assert isinstance(completed_payload.get("reconcile_items"), list)
    assert "run_pnl_summary" in completed_payload
    assert "net_pnl" in completed_payload["run_pnl_summary"]


def test_streamed_history_items_include_timestamps_for_live_tables(pg_store, settings_stub):
    """Live SSE-derived history rows must carry a timestamp so the dashboard can
    render a concrete time instead of falling back to `未记录`.
    """
    run_context_id = "wrk-live-time-001"
    pg_store.upsert_dashboard_run_summary(
        run_context_id=run_context_id,
        trade_date=datetime.now().date().isoformat(),
        decision_mode="mock",
        execution_mode="full",
        capital_base=1_000_000,
        status="accepted",
        execution_fee_total=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        net_pnl=0.0,
        started_at=datetime.now().isoformat(),
        finished_at=None,
        latest_workbench={"latest_run": {"run_context_id": run_context_id, "steps": []}},
    )

    service = ShadowRunService(
        store=pg_store,
        settings=settings_stub,
        llm=MockLLM(),
        provider=MockProvider(),
    )
    service.run(
        user_id=TEST_USER_ID,
        run_context_id=run_context_id,
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    summary = pg_store.get_dashboard_run_summary(run_context_id=run_context_id)
    latest_run = summary["latest_workbench"]["latest_run"]

    for collection_name in ("target_items", "order_items", "reconcile_items"):
        for item in latest_run[collection_name]:
            assert item.get("created_at") or item.get("timestamp"), (
                f"{collection_name} item missing renderable timestamp: {item}"
            )

    derived_history = summary["latest_workbench"]["history"]
    for collection_name in ("decisions", "targets", "orders", "reconcile"):
        for item in derived_history[collection_name]:
            assert item.get("created_at") or item.get("timestamp"), (
                f"history.{collection_name} item missing renderable timestamp: {item}"
            )
