# tests/test_dashboard_sse_reconnect.py
import json
import time

import httpx
import pytest

from src.api.auth_security import create_auth_token
from src.api.dependencies import get_user_runtime_store
from src.core.config import Settings
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


def _seed_completed_run(store: RuntimeStore) -> None:
    store.upsert_dashboard_run_summary(
        run_context_id="wrk-recon-001",
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
        latest_workbench={"latest_run": {"run_context_id": "wrk-recon-001"}},
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
        store.append_dashboard_run_event(
            run_context_id="wrk-recon-001",
            event_type=etype,
            stage=stage,
            status=status,
            payload={"message": msg, "seq": seq},
        )


@pytest.mark.asyncio
async def test_reconnect_with_last_event_id_starts_after_seq(test_app, pg_store, auth_token):
    _seed_completed_run(pg_store)
    test_app.dependency_overrides[get_user_runtime_store] = lambda: pg_store
    transport = httpx.ASGITransport(app=test_app)
    received: list[dict] = []

    settings = Settings()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set(settings.auth_cookie_name, auth_token)
        # 模拟 client 在 seq=2 断开（只看到 1, 2）
        # 然后用 Last-Event-ID: 2 重连
        async with client.stream(
            "GET",
            "/api/v1/dashboard/runs/wrk-recon-001/events",
            headers={"Last-Event-ID": "2"},
        ) as response:
            assert response.status_code == 200
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                received.extend(parse_sse_chunk(chunk))
                if len(received) >= 4:
                    break

    received_ids = [m["id"] for m in received]
    assert received_ids == ["3", "4", "5", "6"]
    assert received[0]["event"] == "stage.updated"
    assert received[-1]["event"] == "run.completed"
