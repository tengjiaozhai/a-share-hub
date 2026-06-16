# Dashboard Trade Run Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze one backend-frontend contract for dashboard trade runs, add a reproducible smoke script, and define the rollout order for shipping the new stream-based run path safely.

**Architecture:** Treat the integration surface as three artifacts: a contract document that names every endpoint and event type, an executable smoke script that starts a run and watches the stream, and operator-facing docs that explain deployment and user verification. Do not keep both the blocking `/api/v1/dashboard/run` UI path and the stream path alive in production; the rollout must switch to the new contract in one release window.

**Tech Stack:** Markdown docs, shell scripts, curl, Python JSON helpers, pytest

---

## Scope Check

This plan is the handoff layer between backend and frontend. It does not add business logic. It defines the contract, validates that both sides obey it, and captures the deployment and smoke-test choreography.

## File Structure

- Create: `docs/dashboard-run-contract.md`
  Freeze the HTTP and SSE contract with request, response, and event payload examples.
- Create: `scripts/run_dashboard_stream_smoke.sh`
  Provide one command-line smoke test for start-run plus SSE replay.
- Create: `tests/test_dashboard_stream_smoke_script.py`
  Lock the smoke script so it continues to exercise the canonical endpoints.
- Modify: `tests/test_docs_alignment.py`
  Assert that the contract doc and user guides mention the new stream path and reconcile fields.
- Modify: `docs/sop.md`
  Explain the new `run_context_id`, reconcile table, and run-PnL summary to end users.
- Modify: `docs/local-aws-sync-guide.md`
  Add the deployment order: migration, backend, frontend, smoke test.

### Task 1: Freeze The Backend-Frontend Contract In One Document

**Files:**
- Create: `docs/dashboard-run-contract.md`
- Modify: `tests/test_docs_alignment.py`

- [ ] **Step 1: Write the failing docs-alignment test**

```python
# tests/test_docs_alignment.py
from pathlib import Path


def test_dashboard_run_contract_mentions_stream_endpoints_and_event_types():
    text = Path("docs/dashboard-run-contract.md").read_text(encoding="utf-8")
    assert "/api/v1/dashboard/runs" in text
    assert "/api/v1/dashboard/runs/{run_context_id}/events" in text
    assert "run.accepted" in text
    assert "stage.updated" in text
    assert "run.completed" in text
    assert "run_pnl_summary" in text
    assert "reconcile_items" in text
```

- [ ] **Step 2: Run the docs-alignment test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py::test_dashboard_run_contract_mentions_stream_endpoints_and_event_types -v
```

Expected: FAIL because `docs/dashboard-run-contract.md` does not exist yet.

- [ ] **Step 3: Write the contract document**

```markdown
<!-- docs/dashboard-run-contract.md -->
# Dashboard Run Contract

## 1. Start run

### Request

`POST /api/v1/dashboard/runs`

```json
{
  "watchlist": ["MRVL", "NBIS", "NVDA", "AAPL", "MU"],
  "capital_base": 10000,
  "max_position_ratio": 0.2,
  "execution_mode": "full",
  "decision_mode": "real",
  "allow_new_positions": true
}
```

### Response

Status: `202 Accepted`

```json
{
  "run_context_id": "wrk-20260615-203007-5ddeec",
  "stream_url": "/api/v1/dashboard/runs/wrk-20260615-203007-5ddeec/events",
  "status": "accepted"
}
```

## 2. Stream events

### Route

`GET /api/v1/dashboard/runs/{run_context_id}/events`

### Event types

- `run.accepted`
- `stage.updated`
- `run.completed`
- `run.failed`

### SSE example

```text
event: stage.updated
data: {"run_context_id":"wrk-20260615-203007-5ddeec","seq":3,"event_type":"stage.updated","stage":"target","status":"done","payload":{"items":[{"symbol":"NVDA","target_quantity":4,"status":"ACTIVE"}],"duration_ms":18}}
```

## 3. Final snapshot

### Route

`GET /api/v1/dashboard/workbench?run_context_id={run_context_id}`

### Required fields

```json
{
  "latest_run": {
    "run_context_id": "wrk-20260615-203007-5ddeec",
    "steps": [],
    "run_pnl_summary": {
      "execution_fee_total": 0.36,
      "realized_pnl": 0.0,
      "unrealized_pnl": -0.60,
      "net_pnl": -0.96
    },
    "reconcile_items": [
      {
        "symbol": "NVDA",
        "quantity": 4,
        "avg_cost": 100.05,
        "mark_price": 99.90,
        "change_pct": -0.0015,
        "unrealized_pnl": -0.60,
        "fee_total": 0.12,
        "mark_time": "2026-06-15T20:30:38+08:00",
        "quote_status": "ok"
      }
    ]
  }
}
```

## 4. Reconciliation route

### Route

`GET /api/v1/reconciliation/status?run_context_id={run_context_id}`

### Rule

The payload returned here must match `latest_run.reconcile_items` for the same `run_context_id`.
```

- [ ] **Step 4: Run the docs-alignment test to verify it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py::test_dashboard_run_contract_mentions_stream_endpoints_and_event_types -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add docs/dashboard-run-contract.md tests/test_docs_alignment.py
git commit -m "docs: freeze dashboard run stream contract"
```

### Task 2: Add A Canonical Smoke Script For Start-Run Plus SSE Replay

**Files:**
- Create: `scripts/run_dashboard_stream_smoke.sh`
- Create: `tests/test_dashboard_stream_smoke_script.py`

- [ ] **Step 1: Write the failing smoke-script test**

```python
# tests/test_dashboard_stream_smoke_script.py
from pathlib import Path


def test_dashboard_stream_smoke_script_uses_new_run_endpoints():
    script = Path("scripts/run_dashboard_stream_smoke.sh").read_text(encoding="utf-8")
    assert "POST /api/v1/dashboard/runs" not in script
    assert 'curl -s -X POST "$BASE_URL/api/v1/dashboard/runs"' in script
    assert 'curl -sN "$BASE_URL/api/v1/dashboard/runs/${RUN_CONTEXT_ID}/events"' in script
    assert 'python3 - <<\'PY\'' in script
    assert 'run.completed' in script
```

- [ ] **Step 2: Run the smoke-script test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_smoke_script.py::test_dashboard_stream_smoke_script_uses_new_run_endpoints -v
```

Expected: FAIL because `scripts/run_dashboard_stream_smoke.sh` does not exist yet.

- [ ] **Step 3: Write the smoke script**

```bash
# scripts/run_dashboard_stream_smoke.sh
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

START_RESPONSE="$(curl -s -X POST "$BASE_URL/api/v1/dashboard/runs" \
  -H 'Content-Type: application/json' \
  --data '{"watchlist":["NVDA","AAPL"],"capital_base":10000,"max_position_ratio":0.2,"execution_mode":"full","decision_mode":"real","allow_new_positions":true}')"

RUN_CONTEXT_ID="$(python3 - <<'PY' "$START_RESPONSE"
import json
import sys

payload = json.loads(sys.argv[1])
print(payload["run_context_id"])
PY
)"

echo "run_context_id=$RUN_CONTEXT_ID"

curl -sN "$BASE_URL/api/v1/dashboard/runs/${RUN_CONTEXT_ID}/events" | python3 - <<'PY'
import json
import sys

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line.startswith("data: "):
        continue
    payload = json.loads(line[6:])
    print(f"{payload['seq']} {payload['event_type']} {payload['stage']} {payload['status']}")
    if payload["event_type"] == "run.completed":
        break
PY

curl -s "$BASE_URL/api/v1/dashboard/workbench?run_context_id=${RUN_CONTEXT_ID}" | python3 - <<'PY'
import json
import sys

payload = json.load(sys.stdin)
summary = payload["latest_run"]["run_pnl_summary"]
print(f"net_pnl={summary['net_pnl']}")
print(f"reconcile_count={len(payload['latest_run']['reconcile_items'])}")
PY
```

- [ ] **Step 4: Run the smoke-script test to verify it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_stream_smoke_script.py::test_dashboard_stream_smoke_script_uses_new_run_endpoints -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add scripts/run_dashboard_stream_smoke.sh tests/test_dashboard_stream_smoke_script.py
git commit -m "test: add dashboard run stream smoke script"
```

### Task 3: Document The Rollout Order And User-Facing Validation

**Files:**
- Modify: `docs/sop.md`
- Modify: `docs/local-aws-sync-guide.md`
- Modify: `tests/test_docs_alignment.py`

- [ ] **Step 1: Write the failing docs-alignment tests for rollout and SOP**

```python
# tests/test_docs_alignment.py
def test_sop_mentions_run_trace_and_reconcile_fields():
    text = Path("docs/sop.md").read_text(encoding="utf-8")
    assert "run_context_id" in text
    assert "成本价" in text
    assert "现价" in text
    assert "未实现盈亏" in text


def test_local_aws_sync_guide_mentions_stream_release_order():
    text = Path("docs/local-aws-sync-guide.md").read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "先部署后端，再部署前端，并在同一发布窗口切换到 `/api/v1/dashboard/runs`" in text
    assert "scripts/run_dashboard_stream_smoke.sh" in text
```

- [ ] **Step 2: Run the docs-alignment tests to verify they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py::test_sop_mentions_run_trace_and_reconcile_fields tests/test_docs_alignment.py::test_local_aws_sync_guide_mentions_stream_release_order -v
```

Expected: FAIL because the current docs do not mention the new run trace, reconcile fields, or stream cutover order.

- [ ] **Step 3: Update the user and operator docs**

```markdown
<!-- docs/sop.md -->
## 本轮运行完成后先看 3 个地方

1. `run_context_id`
   - 每一轮运行都有一个唯一编号。
   - 页面顶部显示的 `run_context_id`，必须能和时间线、接口返回、服务日志对上同一轮。

2. `本轮盈亏摘要`
   - `本轮净影响`：这轮运行对账户净值的总影响。
   - `执行成本`：手续费和滑点带来的成本。
   - `持仓浮盈亏`：按对账时点的现价计算出来的浮动盈亏。

3. `对账`
   - `成本价`：你这只股票的持仓平均成本。
   - `现价`：本轮对账用到的价格。
   - `未实现盈亏`：如果现在平仓，账面上大概赚亏多少。
   - `行情时间`：这次对账使用的是哪一个时点的行情。
```

```markdown
<!-- docs/local-aws-sync-guide.md -->
## Dashboard stream release order

1. 运行数据库迁移：

```bash
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

2. 部署后端代码，确认以下接口返回正常：
   - `POST /api/v1/dashboard/runs`
   - `GET /api/v1/dashboard/runs/{run_context_id}/events`
   - `GET /api/v1/dashboard/workbench?run_context_id={run_context_id}`

3. 部署前端代码。

4. 先部署后端，再部署前端，并在同一发布窗口切换到 `/api/v1/dashboard/runs`，不要长期同时保留旧的阻塞式页面交互路径。

5. 运行 smoke：

```bash
bash scripts/run_dashboard_stream_smoke.sh http://13.214.201.113:8000
```
```

- [ ] **Step 4: Run the docs-alignment tests to verify they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py::test_sop_mentions_run_trace_and_reconcile_fields tests/test_docs_alignment.py::test_local_aws_sync_guide_mentions_stream_release_order -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add docs/sop.md docs/local-aws-sync-guide.md tests/test_docs_alignment.py
git commit -m "docs: add dashboard run stream rollout guidance"
```

## Self-Review

**Spec coverage**

- 后端和前端如何对接: Task 1 freezes the canonical contract.
- 如何验证整条流式链路: Task 2 adds a repeatable smoke script.
- 如何发布避免旧路径和新路径打架: Task 3 writes the rollout order and user/operator checks.

**Placeholder scan**

- No placeholder markers remain.
- Every task includes concrete file paths, code or doc content, exact commands, and expected outcomes.

**Type consistency**

- Canonical start endpoint: `/api/v1/dashboard/runs`
- Canonical stream endpoint: `/api/v1/dashboard/runs/{run_context_id}/events`
- Canonical final snapshot field names: `run_pnl_summary`, `reconcile_items`, `run_context_id`
- Canonical smoke script: `scripts/run_dashboard_stream_smoke.sh`
