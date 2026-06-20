# tests/test_dashboard_sse_eventstream.py
import asyncio
import json
import time

import httpx
import pytest

from src.core.config import Settings
from src.main import build_app
from src.api.dependencies import get_user_runtime_store
from src.storage.runtime_store import RuntimeStore


SSE_DELIMITER = b"\r\n\r\n"


def parse_sse_chunk(chunk: bytes) -> list[dict]:
    """Parse one SSE message block (terminated by \\r\\n\\r\\n) into {event, data, id}."""
    messages: list[dict] = []
    for block in chunk.split(SSE_DELIMITER):
        block = block.strip()
        if not block:
            continue
        event_name = None
        event_id = None
        data_lines: list[str] = []
        for line in block.split(b"\n"):
            line = line.rstrip(b"\r")
            if line.startswith(b"event: "):
                event_name = line[len(b"event: "):].decode("utf-8")
            elif line.startswith(b"id: "):
                event_id = line[len(b"id: "):].decode("utf-8")
            elif line.startswith(b"data: "):
                data_lines.append(line[len(b"data: "):].decode("utf-8"))
        if data_lines:
            messages.append(
                {
                    "event": event_name,
                    "id": event_id,
                    "data": json.loads("\n".join(data_lines)),
                }
            )
    return messages


@pytest.fixture
def seeded_store(pg_store: RuntimeStore):
    pg_store.upsert_dashboard_run_summary(
        run_context_id="wrk-sse-001",
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
        latest_workbench={"latest_run": {"run_context_id": "wrk-sse-001"}},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="run.accepted",
        stage="decision",
        status="running",
        payload={"message": "请求已受理"},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="stage.updated",
        stage="decision",
        status="done",
        payload={"items": [{"symbol": "NVDA", "action": "BUY"}]},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="stage.updated",
        stage="target",
        status="done",
        payload={"items": [{"symbol": "NVDA", "target_quantity": 4}]},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="stage.updated",
        stage="execute",
        status="done",
        payload={"items": [{"symbol": "NVDA", "fill_price": 100.05}]},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="stage.updated",
        stage="reconcile",
        status="done",
        payload={"reconcile_items": [{"symbol": "NVDA", "mark_price": 99.90}]},
    )
    pg_store.append_dashboard_run_event(
        run_context_id="wrk-sse-001",
        event_type="run.completed",
        stage="reconcile",
        status="done",
        payload={"run_pnl_summary": {"net_pnl": -0.96}},
    )
    return pg_store


@pytest.mark.asyncio
async def test_sse_response_streams_all_six_events_for_completed_run(test_app, seeded_store, auth_token):
    test_app.dependency_overrides[get_user_runtime_store] = lambda: seeded_store
    transport = httpx.ASGITransport(app=test_app)
    received: list[dict] = []
    chunk_timestamps: list[float] = []
    cookie_name = Settings().auth_cookie_name

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set(cookie_name, auth_token)
        async with client.stream(
            "GET", "/api/v1/dashboard/runs/wrk-sse-001/events"
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                chunk_timestamps.append(time.monotonic())
                received.extend(parse_sse_chunk(chunk))
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
    assert received[-1]["data"]["event_type"] == "run.completed"
