# tests/test_dashboard_sse_pacing.py
import time

import pytest

from src.api.routes_dashboard import stream_dashboard_run_events
from src.api.dependencies import get_user_runtime_store
from src.storage.runtime_store import RuntimeStore


def _seed_completed_run(store: RuntimeStore, run_context_id: str = "wrk-pacing-001") -> None:
    store.upsert_dashboard_run_summary(user_id="test-user", 
        run_context_id=run_context_id,
        trade_date="2026-06-16",
        decision_mode="mock",
        execution_mode="full",
        capital_base=10_000,
        status="completed",
        execution_fee_total=0.36,
        realized_pnl=0.0,
        unrealized_pnl=-0.60,
        net_pnl=-0.96,
        started_at="2026-06-16T14:00:00+08:00",
        finished_at="2026-06-16T14:00:17+08:00",
        latest_workbench={"latest_run": {"run_context_id": run_context_id}},
    )
    for seq, (etype, stage, status, msg) in enumerate(
        [
            ("run.accepted", "decision", "running", "ok"),
            ("stage.updated", "decision", "done", "decided"),
            ("stage.updated", "target", "done", "targeted"),
            ("stage.updated", "execute", "done", "executed"),
            ("stage.updated", "reconcile", "done", "reconciled"),
            ("run.completed", "reconcile", "done", "done"),
        ],
        start=1,
    ):
        store.append_dashboard_run_event(user_id="test-user", 
            run_context_id=run_context_id,
            event_type=etype,
            stage=stage,
            status=status,
            payload={"message": msg, "seq": seq},
        )


@pytest.fixture
def seeded_store(pg_store: RuntimeStore):
    _seed_completed_run(pg_store, "wrk-pacing-001")
    return pg_store


@pytest.mark.asyncio
async def test_sse_paces_yields_so_browser_event_source_can_dispatch(test_app, seeded_store):
    """Verify that event_iter paces its yields so a browser EventSource can
    dispatch each event before the connection closes.

    Without per-yield sleep the 6 events flush in <1s and EventSource
    never fires onmessage, forcing a 47s reconnect. With 50ms pacing the
    spread between first and last event must comfortably exceed 100ms.

    Note: we iterate ``response.body_iterator`` (the ``event_iter`` generator)
    directly rather than going through ``httpx.AsyncClient.stream()`` because
    httpx's ``ASGITransport`` coalesces all SSE body chunks into a single
    concatenated byte string, which would mask per-yield pacing. A real
    browser over a real socket observes each yield as a distinct chunk, so
    the generator-level pacing we test here is what reaches the browser.
    """
    test_app.dependency_overrides[get_user_runtime_store] = lambda: seeded_store

    response = await stream_dashboard_run_events(
        run_context_id="wrk-pacing-001",
        last_event_id=None,
        store=seeded_store,
    )

    event_timestamps: list[float] = []
    received: list[dict] = []
    async for event in response.body_iterator:
        event_timestamps.append(time.monotonic())
        received.append(event)
        if len(received) >= 6:
            break

    assert [m["event"] for m in received] == [
        "run.accepted",
        "stage.updated",
        "stage.updated",
        "stage.updated",
        "stage.updated",
        "run.completed",
    ]
    assert [m["id"] for m in received] == ["1", "2", "3", "4", "5", "6"]

    assert len(event_timestamps) == 6
    spread_ms = (event_timestamps[-1] - event_timestamps[0]) * 1000
    # 6 events × 50ms pacing = ~250ms minimum spread across the 5 inter-event
    # gaps. Use 100ms as a conservative lower bound to catch regressions
    # where the per-yield sleep was removed or shrunk below the browser's
    # dispatch window.
    assert spread_ms > 100, (
        f"Expected spread > 100ms between first and last event, got {spread_ms:.1f}ms. "
        "Browser EventSource needs pacing to dispatch events before connection close."
    )
