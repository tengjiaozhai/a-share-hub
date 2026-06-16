"""Tests for ShadowRunService.run() — the background task that drives
dashboard trade runs. These tests assert:

1. run() emits the full stage sequence (decision → target → execute → reconcile)
   followed by run.completed.
2. run() persists a complete latest_workbench payload that the front-end
   expects (history / risk / performance / latest_run.run_pnl_summary, etc).
3. run() emits run.failed and marks summary.status="failed" when any stage
   raises.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.execution.shadow_run_service import ShadowRunService


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
        run_context_id="wrk-test-1",
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    events = pg_store.list_dashboard_run_events("wrk-test-1")
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
        run_context_id="wrk-test-2",
        config={"watchlist": ["NVDA"], "decision_mode": "mock", "capital_base": 1_000_000},
    )

    summary = pg_store.get_dashboard_run_summary("wrk-test-2")
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
        run_context_id="wrk-test-3",
        config={"watchlist": ["NVDA"], "decision_mode": "real", "capital_base": 1_000_000},
    )

    summary = pg_store.get_dashboard_run_summary("wrk-test-3")
    assert summary["status"] == "failed"

    events = pg_store.list_dashboard_run_events("wrk-test-3")
    assert any(e["event_type"] == "run.failed" for e in events)
