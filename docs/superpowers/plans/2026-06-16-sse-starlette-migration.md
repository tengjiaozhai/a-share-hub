# Dashboard SSE sse-starlette 改造计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `routes_dashboard.py` 的 SSE 端点从手写 `StreamingResponse` 替换为 `sse-starlette` 的 `EventSourceResponse`，让浏览器 `EventSource` 真正能持续接收事件流，timeline 4 stage 实时出现，pnl 卡片实时更新。

**Architecture:** SSE 端点保持 async generator 形式 (`event_iter`)，但 yield 改为 `{id, event, data}` 三元 dict。`EventSourceResponse` 负责三件手写 StreamingResponse 做不好的事：(1) 每次 yield 后立即 flush h11 transport 缓冲区；(2) 每 15s 自动发 `: ping\n\n` 注释心跳；(3) 通过 `Last-Event-ID` 协议支持断线重连。前端 `dashboard_run.js` 不需要改，`new EventSource` API 兼容。运行时依赖新增 `sse-starlette>=2.1.0`。

**Tech Stack:** FastAPI 0.135+、sse-starlette 2.1+、httpx（流式测试）、pytest、现有 RuntimeStore (SQLAlchemy + SQLite 测试) 、Playwright（e2e 浏览器验证）

---

## 解决的遗留问题（产品可理解版）

**根因**：后端的"流式"逻辑没问题（curl 验证能分批），但当 client 端带 `Accept: text/event-stream` 时，Starlette/FastAPI 的 `StreamingResponse` 在 async generator + chunked encoding + SSE headers 组合下，行为变成"立即一次性 flush 全部 + close connection"，而不是"长连接持续 push"。

**后果**：
- 浏览器 `EventSource` 看到连接瞬间关闭 → 视为错误 → 反复自动重连，**永远收不到一个完整 message**
- 前端 `connectRunStream` 里 `runEventSource.onmessage` 永远不触发 → timeline 不更新、pnl 不更新

**为什么 `sse-starlette.EventSourceResponse` 能修**：
1. 它在每次 `yield` 后通过 `asyncio` task 显式驱动 h11 transport 写 chunk，绕过 Starlette 默认的 chunked buffer
2. 它内置 `ping=15` 心跳协程，浏览器 `EventSource` 不会判定连接死亡
3. 它解析 `Last-Event-ID` 头并把它作为 `last_event_id` 注入 generator，支持断线重连
4. 它把 SSE message 拼装 (`event: ...\ndata: ...\nid: ...\n\n`) 和 chunked encoding 分离，不会让 chunked flush 与 message 边界混在一起

---

## Scope Check

本计划只覆盖 SSE 流式传输层。**不在本计划范围**：
- `shadow_run_service.py` 内部业务逻辑（已可用 mock 模式跑通）
- 前端 UI 渲染（`renderTimeline` / `renderRunPnlSummary` / `renderReconcile` 已与新 payload 契约兼容）
- A 股 / 美股 watchlist chips 修复（`us_stock.js` + `market.js` 的 `data.items` 兜底在上一轮已完成）
- 数据库 schema（`dashboard_run_summaries` / `dashboard_run_events` 不变）
- 部署层 nginx SSE 头（运维侧，前端不动）

## File Structure

- **Modify**: `pyproject.toml`
  在 `dependencies` 列表加 `sse-starlette>=2.1.0`。
- **Modify**: `src/api/routes_dashboard.py:198-228`
  `stream_dashboard_run_events` 路由重写：用 `EventSourceResponse` 替代 `StreamingResponse`；`event_iter` yield dict。
- **Create**: `tests/test_dashboard_sse_eventstream.py`
  端到端测试用 `httpx.AsyncClient` 流式 GET，解析 SSE 协议，断言 6 个 events 是分批到达（不是一次性），并验证 chunked encoding 在 live run 模式下持续 push。
- **Create**: `tests/test_dashboard_sse_reconnect.py`
  断线重连测试：模拟 client 在 seq=2 断开后用 `Last-Event-ID: 2` 重连，断言从 seq=3 开始收到事件。
- **Modify**: `tests/test_dashboard_stream_api.py:31-83`
  旧 `test_run_events_route_streams_ordered_event_log` 改为验证新 dict payload 格式（`run.accepted` 仍然在 response 中），并删除对 StreamingResponse 内部 byte 拼接的过度耦合断言。
- **Modify**: `docs/sop.md`
  增加一节解释 sse-starlette 的角色 + 浏览器 EventSource 30s timeout 排查。

---

### Task 1: 添加 sse-starlette 依赖

**Files:**
- Modify: `pyproject.toml:12-28`

- [ ] **Step 1: 加依赖到 pyproject.toml**

在 `pyproject.toml` 第 20 行（`fastapi>=0.135.0` 之后）插入一行：

```toml
    "fastapi>=0.135.0",
    "sse-starlette>=2.1.0",
    "uvicorn>=0.24.0",
```

- [ ] **Step 2: 安装新依赖**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/pip install -e ".[dev]"
```

Expected: 安装成功，`Successfully installed sse-starlette-2.x.x`。

- [ ] **Step 3: 验证 import**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -c "from sse_starlette.sse import EventSourceResponse; print('ok')"
```

Expected: 输出 `ok`。

- [ ] **Step 4: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add pyproject.toml
git commit -m "chore: add sse-starlette dependency"
```

---

### Task 2: 写失败的端到端测试 — 验证 SSE 事件真正分批到达

**Files:**
- Create: `tests/test_dashboard_sse_eventstream.py`

- [ ] **Step 1: 写测试 — 模拟已完成的 run，验证 6 个 events 全部到达**

```python
# tests/test_dashboard_sse_eventstream.py
import asyncio
import json
import time

import httpx
import pytest

from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.runtime_store import RuntimeStore


SSE_DELIMITER = b"\n\n"


def parse_sse_chunk(chunk: bytes) -> list[dict]:
    """Parse one SSE message block (terminated by \\n\\n) into {event, data, id}."""
    messages: list[dict] = []
    for block in chunk.split(SSE_DELIMITER):
        block = block.strip()
        if not block:
            continue
        event_name = None
        event_id = None
        data_lines: list[str] = []
        for line in block.split(b"\n"):
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
async def test_sse_response_streams_all_six_events_for_completed_run(test_app, seeded_store):
    test_app.dependency_overrides[get_runtime_store] = lambda: seeded_store
    transport = httpx.ASGITransport(app=test_app)
    received: list[dict] = []
    chunk_timestamps: list[float] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
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
```

- [ ] **Step 2: 跑测试，验证它失败**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_eventstream.py -v
```

Expected: FAIL — 因为 `routes_dashboard.py:198` 还是 `StreamingResponse` + 旧 byte 拼接格式，response header 缺 `x-accel-buffering`，parse 出来的 `event/id` 字段为 None（手写格式是 `event: ...\ndata: ...\n\n` 没有 `id:` 行）。

- [ ] **Step 3: Commit（保留失败测试）**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add tests/test_dashboard_sse_eventstream.py
git commit -m "test: assert sse response has expected headers and id field"
```

---

### Task 3: 用 sse-starlette.EventSourceResponse 重写 stream 端点

**Files:**
- Modify: `src/api/routes_dashboard.py:1-16, 198-228`

- [ ] **Step 1: 加 import**

在 `src/api/routes_dashboard.py` 第 7 行（`from fastapi.responses import HTMLResponse, StreamingResponse`）改为：

```python
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
```

- [ ] **Step 2: 重写 `stream_dashboard_run_events` 路由**

把 `src/api/routes_dashboard.py:198-228` 整段替换为：

```python
@router.get("/api/v1/dashboard/runs/{run_context_id}/events")
async def stream_dashboard_run_events(
    run_context_id: str,
    last_event_id: str | None = Query(default=None),
    store: RuntimeStore = Depends(get_runtime_store),
) -> EventSourceResponse:
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def event_iter():
        last_seq = after_seq
        while True:
            events = store.list_dashboard_run_events(run_context_id, after_seq=last_seq)
            for event in events:
                last_seq = event["seq"]
                yield {
                    "id": str(event["seq"]),
                    "event": event["event_type"],
                    "data": json.dumps(event, ensure_ascii=True),
                }
            summary = store.get_dashboard_run_summary(run_context_id)
            if summary and summary["status"] in {"completed", "failed"}:
                return
            await asyncio.sleep(0.2)

    return EventSourceResponse(
        event_iter(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

注意：
- 路由函数改为 `async def`（之前是 `def`），`EventSourceResponse` 需要 async generator 而 sync 路由在 threadpool 里跑
- `last_event_id` Query 参数对应 SSE `Last-Event-ID` 头，sse-starlette 自动注入
- `event_iter` 不再 yield byte 字符串，yield dict 让 sse-starlette 自己拼装
- `ping=15` 让 sse-starlette 每 15s 发 `: ping\n\n` 注释
- `asyncio` 已在上一轮 import 过（`import asyncio`），不需要再加

- [ ] **Step 3: 跑测试，验证通过**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_eventstream.py -v
```

Expected: PASS — response headers 含 `x-accel-buffering: no` + `cache-control: no-cache`，6 个 events 全部到达，每个有 `id: <seq>`。

- [ ] **Step 4: 跑现有 dashboard 流式测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_api.py -v
```

Expected: PASS — `test_start_run_returns_accepted_and_run_context_id` 与 `test_run_events_route_streams_ordered_event_log` 仍应通过（POST 端点没改；SSE 端点 body 仍是 6 个 `run.accepted` / `stage.updated` / `run.completed`，只是拼装方式变了）。

如果 `test_run_events_route_streams_ordered_event_log` 失败（它对 `event:` 前缀做了字符串包含断言），跳到 Task 4 修。

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py
git commit -m "feat: switch dashboard stream endpoint to sse-starlette EventSourceResponse"
```

---

### Task 4: 调整 test_dashboard_stream_api.py 旧测试以适配新格式

**Files:**
- Modify: `tests/test_dashboard_stream_api.py:31-83`

- [ ] **Step 1: 看旧测试完整内容**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
sed -n '31,90p' tests/test_dashboard_stream_api.py
```

- [ ] **Step 2: 改写 `test_run_events_route_streams_ordered_event_log`**

如果 Task 3 跑旧测试失败，原因是 `assert '"run_context_id": "wrk-001"' in body` 之类的字符串包含断言假设 SSE 格式特定。新版用 `id:` 行和 dict payload，需要重写。

替换 `tests/test_dashboard_stream_api.py:45-83`（`test_run_events_route_streams_ordered_event_log` 整段）为：

```python
def test_run_events_route_streams_ordered_event_log(test_app, pg_store):
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

    client = TestClient(test_app)
    with client.stream("GET", "/api/v1/dashboard/runs/wrk-001/events") as response:
        body = "".join(
            chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            for chunk in response.iter_text()
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
    assert "event: run.accepted" in body
    assert "event: run.completed" in body
    assert "id: 1" in body
    assert "id: 2" in body
    assert '"run_context_id": "wrk-001"' in body
```

- [ ] **Step 3: 跑测试，验证通过**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_api.py -v
```

Expected: PASS。

- [ ] **Step 4: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add tests/test_dashboard_stream_api.py
git commit -m "test: adapt dashboard stream test to sse-starlette payload"
```

---

### Task 5: 写断线重连测试 — 验证 Last-Event-ID 协议

**Files:**
- Create: `tests/test_dashboard_sse_reconnect.py`

- [ ] **Step 1: 写测试 — client 在 seq=2 断开后用 Last-Event-ID 重连**

```python
# tests/test_dashboard_sse_reconnect.py
import json
import time

import httpx
import pytest

from src.storage.dependencies import get_runtime_store
from src.storage.runtime_store import RuntimeStore


SSE_DELIMITER = b"\n\n"


def parse_sse_chunk(chunk: bytes) -> list[dict]:
    messages: list[dict] = []
    for block in chunk.split(SSE_DELIMITER):
        block = block.strip()
        if not block:
            continue
        event_name = None
        event_id = None
        data_lines: list[str] = []
        for line in block.split(b"\n"):
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
async def test_reconnect_with_last_event_id_starts_after_seq(test_app, pg_store):
    _seed_completed_run(pg_store)
    test_app.dependency_overrides[get_runtime_store] = lambda: pg_store
    transport = httpx.ASGITransport(app=test_app)
    received: list[dict] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
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
```

- [ ] **Step 2: 跑测试，验证它失败（Task 3 没实现 last_event_id 注入）**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_reconnect.py -v
```

Expected: FAIL — 收到的事件 id 应该是 `["3", "4", "5", "6"]` 但实际会收到 `["1", "2", "3", "4", "5", "6"]`（last_event_id 没被使用）。

- [ ] **Step 3: 让 `routes_dashboard.py` 路由接 `last_event_id` Query 参数并传给 generator**

如果 Task 3 已经把 `last_event_id: str | None = Query(default=None)` 加进签名，**还需要**让 sse-starlette 把它作为 initial value 传给 generator。检查 sse-starlette 文档 / 源码：传入 `EventSourceResponse` 的 `data` 字段如果是个 callable / `Depends` 函数，可以传额外参数。

**改 `src/api/routes_dashboard.py:198-228` 整段**为：

```python
from fastapi import Query
from sse_starlette.sse import EventSourceResponse


@router.get("/api/v1/dashboard/runs/{run_context_id}/events")
async def stream_dashboard_run_events(
    run_context_id: str,
    last_event_id: str | None = Query(default=None),
    store: RuntimeStore = Depends(get_runtime_store),
) -> EventSourceResponse:
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def event_iter():
        last_seq = after_seq
        while True:
            events = store.list_dashboard_run_events(run_context_id, after_seq=last_seq)
            for event in events:
                last_seq = event["seq"]
                yield {
                    "id": str(event["seq"]),
                    "event": event["event_type"],
                    "data": json.dumps(event, ensure_ascii=True),
                }
            summary = store.get_dashboard_run_summary(run_context_id)
            if summary and summary["status"] in {"completed", "failed"}:
                return
            await asyncio.sleep(0.2)

    return EventSourceResponse(
        event_iter(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

注意：`Query(default=None)` 让 FastAPI 在请求进来时把 `Last-Event-ID` 头映射到 `last_event_id` 变量（sse-starlette 内部处理），然后路由函数用 `int(last_event_id)` 计算 `after_seq`，闭包捕获这个值传给 `event_iter`。

- [ ] **Step 4: 跑测试，验证通过**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_reconnect.py -v
```

Expected: PASS — 重连后只收到 seq 3, 4, 5, 6。

- [ ] **Step 5: 跑全部 SSE 相关测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_eventstream.py tests/test_dashboard_sse_reconnect.py tests/test_dashboard_stream_api.py -v
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py tests/test_dashboard_sse_reconnect.py
git commit -m "feat: support SSE Last-Event-ID reconnect from after_seq"
```

---

### Task 6: 验证浏览器 EventSource 真实行为（端到端）

**Files:**
- 不修改代码
- 创建临时验证脚本：`/Volumes/PortableSSD/tin/trial-production/output/dashboard-trade-run-verify/sse-browser-verify.sh`（不写入仓库）

- [ ] **Step 1: 启动后端**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

Expected: 启动后 `Application startup complete.`，监听 8000。

- [ ] **Step 2: 用 Playwright 真实浏览器验证**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh open http://localhost:8000/dashboard
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh eval "(() => { window.__sseLog = []; const orig = window.EventSource; window.EventSource = function(url, cfg) { const es = new orig(url, cfg); window.__sseT0 = performance.now(); const oon = es.onmessage; es.onmessage = (ev) => { window.__sseLog.push({t: Math.round(performance.now() - window.__sseT0), event: 'msg', data: (ev.data||'').slice(0, 60)}); if (oon) oon.call(es, ev); }; const oAdd = es.addEventListener.bind(es); es.addEventListener = (t, h, opts) => { const wrapped = (ev) => { window.__sseLog.push({t: Math.round(performance.now() - window.__sseT0), event: t, data: (ev.data||'').slice(0, 60)}); return h(ev); }; return oAdd(t, wrapped, opts); }; es.addEventListener('open', () => window.__sseLog.push({t: 0, event: 'open'})); es.addEventListener('error', (e) => window.__sseLog.push({t: Math.round(performance.now() - window.__sseT0), event: 'error', rs: es.readyState})); return es; }; window.EventSource.prototype = orig.prototype; return 'patched'; })()"
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh click 16
sleep 35
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh eval "JSON.stringify({stream: document.getElementById('stream-status').textContent, timelineCount: document.querySelectorAll('#timeline .tl-step').length, pnlNet: document.getElementById('run-pnl-net').textContent, sse: (window.__sseLog || []).map(e => e.event + '@' + e.t + 'ms ' + (e.data || '').slice(0, 40))})"
```

Expected:
- `stream`: 「本轮完成」(success pill) 或「运行中」持续中
- `timelineCount`: 4 (4 个 stage 全部出现)
- `pnlNet`: 真实 net_pnl 数字（不再是 `CNY 0.00`）
- `sse` 列表中至少 6 条 `msg@<X>ms` 且时间戳分散（不是全部 0ms），有 `stage.updated`/`run.completed` 命名事件

- [ ] **Step 3: 截图保存**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh screenshot /Volumes/PortableSSD/tin/trial-production/output/dashboard-trade-run-verify/sse-starlette-verify.png
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh close
```

Expected: 截图保存到指定路径。timeline 4 stage 全部出现、pnl 数字非 0、stream pill 显示「本轮完成」。

- [ ] **Step 4: 不需要 commit（验证脚本不在仓库）**

---

### Task 7: 更新 sop.md 文档

**Files:**
- Modify: `docs/sop.md`

- [ ] **Step 1: 看 sop.md 现有内容**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
sed -n '1,50p' docs/sop.md
```

- [ ] **Step 2: 在「本轮运行完成后先看 3 个地方」章节后追加一节**

在 `docs/sop.md` 末尾追加：

```markdown
## 浏览器 SSE 流式看不到事件的排查

如果点击「运行一轮模拟交易」后，timeline 停在第一个 stage 不动，pnl 始终 0.00，stream pill 显示「运行超时」：

1. **检查后端响应头**

   ```bash
   curl -sI -X POST http://localhost:8000/api/v1/dashboard/runs \
     -H 'Content-Type: application/json' --data '{"watchlist":["NVDA"]}'
   curl -sI "http://localhost:8000/api/v1/dashboard/runs/<run_context_id>/events"
   ```

   期望看到：
   - `content-type: text/event-stream; charset=utf-8`
   - `cache-control: no-cache`
   - `x-accel-buffering: no`
   - `connection: keep-alive`

2. **检查 nginx 反代**（如果部署在 nginx 后面）：确保 `location /api/v1/dashboard/runs/` 段有 `proxy_buffering off;` 和 `add_header Cache-Control no-cache;`。

3. **检查 sse-starlette 版本**：`pip show sse-starlette`，版本需要 >= 2.1.0，更早版本在 Starlette 0.27+ 上有 chunked-encoding 立即关闭 bug。

4. **测试断线重连**：浏览器 DevTools Network 面板 → 找 EventSource 连接 → 右键 → "Reconnect"，应能从 `Last-Event-ID` 之后继续。
```

- [ ] **Step 3: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add docs/sop.md
git commit -m "docs: add SSE troubleshooting section to sop"
```

---

### Task 8: 最终全量验证

**Files:**
- 不修改代码

- [ ] **Step 1: 跑全部 SSE 相关测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_sse_eventstream.py tests/test_dashboard_sse_reconnect.py tests/test_dashboard_stream_api.py tests/test_dashboard_api.py -v
```

Expected: 全部 PASS。

- [ ] **Step 2: 跑 lint**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/api/routes_dashboard.py tests/test_dashboard_sse_eventstream.py tests/test_dashboard_sse_reconnect.py tests/test_dashboard_stream_api.py
```

Expected: 0 errors（line-length 120 已遵守）。

- [ ] **Step 3: 跑类型检查**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m mypy src/api/routes_dashboard.py
```

Expected: 0 errors。

- [ ] **Step 4: 浏览器端到端冒烟（如果还没做 Task 6）**

执行 Task 6 Step 1-3 验证浏览器 EventSource 能收到 6 个事件 + timeline 4 stage + pnl 数字更新。

- [ ] **Step 5: 看 git log 确认 commit 序列**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git log --oneline -10
```

Expected: 看到 6-7 个 commit，从 `chore: add sse-starlette dependency` 开始，到 `docs: add SSE troubleshooting section to sop` 结束。

---

## Self-Review

**Spec coverage**（来自产品验收要求）：

- ✅ 「用 sse-starlette 改造」 → Task 1（装依赖）、Task 3（重写端点）
- ✅ 「浏览器 EventSource 持续 push」 → Task 3（EventSourceResponse 替换 StreamingResponse）、Task 6（端到端验证）
- ✅ 「断线重连」 → Task 5（Last-Event-ID 协议）
- ✅ 「根因解释（产品可理解版）」 → 计划顶部「解决的遗留问题」章节
- ✅ 「sse-starlette 为什么能修」 → 计划顶部 4 个机制说明
- ✅ 「端到端测试覆盖」 → Task 2 + Task 5 + Task 6
- ✅ 「旧测试不破坏」 → Task 4
- ✅ 「文档同步」 → Task 7

**Placeholder scan**：

- 0 个 "TBD" / "TODO" / "implement later" / "fill in details"
- 0 个 "add appropriate error handling" / "handle edge cases"
- 0 个 "Similar to Task N" — 每个 task 重复的代码都写完整
- 所有 code-changing step 都含完整代码块
- 所有 named type/function 在使用前都有定义（`EventSourceResponse` 在 Task 1 import；`pg_store` fixture 在 conftest.py 已存在；`parse_sse_chunk` 在 Task 2 / Task 5 自定义；`seeded_store` 是 Task 2 内的 fixture）

**Type consistency**：

- `event_iter` 始终是 `async def` generator，yield dict `{id, event, data}`（Task 3 + Task 5 一致）
- `last_event_id` Query 参数名一致（Task 3 + Task 5）
- `parse_sse_chunk` 函数签名 `(chunk: bytes) -> list[dict]` 在 Task 2 和 Task 5 一样
- `pg_store.upsert_dashboard_run_summary` / `append_dashboard_run_event` 参数名一致
- `EventSourceResponse` 的 `ping=15` 在 Task 3 + Task 5 一致

**风险**：

- sse-starlette 与 FastAPI 0.135+ 兼容性：sse-starlette 2.1+ 官方支持 Starlette 0.36+，FastAPI 0.135 依赖 Starlette 0.36+。如果跑测试遇到 `ImportError: cannot import name '...' from 'starlette.requests'`，把 sse-starlette 锁到 2.2.x。
- 如果 Task 3 Step 4 旧测试失败但 Task 4 不能直接修（因为 Task 3 还没确认是 `event:` 格式变了），先在 Task 3 看实际 response body 是什么，再决定 Task 4 怎么改。
- Task 6 浏览器验证依赖 `bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh` 可用。如果不可用，跳过 Task 6 改用 curl + `curl -sN --max-time 30` 抓 5 秒看事件分批即可。
