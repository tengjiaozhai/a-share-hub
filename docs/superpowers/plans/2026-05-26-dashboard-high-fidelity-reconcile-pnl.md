# Dashboard 对账与盈亏高保真复刻实施计划

## 执行结果（2026-05-26）

- 已完成：完整链路补齐为 `决策 -> 目标仓位 -> 执行 -> 对账`，并在 `risk.daily_pnl` 与“对账 done 节点”同时展示模拟盈亏。
- 已完成：时间线条目在轮询刷新后保持原型顺序（按输入观察列表顺序输出决策、目标仓位、执行）。
- 已完成：前端“对账”节点对 `+¥/-¥` 盈亏片段做绿色高亮渲染。
- 已完成：RuntimeStore 新增执行单状态推进与当日盈亏聚合能力（`update_execution_order_status`、`sum_daily_pnl`）。

### 验收证据

- API 验收：`POST /api/v1/dashboard/run` 返回 `risk.daily_pnl`，且 `latest_run.steps` 末尾为 `reconcile/running` + `reconcile/done`。
- UI 验收：通过浏览器实操运行一轮后，页面展示“对账”节点与“模拟盈亏: +¥1,250”，风险卡展示 `+¥1,250.00`。
- 测试验收：
  - `tests/test_dashboard_api.py::test_run_endpoint_contains_reconcile_stage_and_daily_pnl`
  - `tests/test_dashboard_api.py::test_decision_mode_marks_reconcile_as_skipped`
  - `tests/test_runtime_store_pg.py::test_runtime_store_can_mark_execution_order_filled_and_sum_daily_pnl`
  - 结果：`3 passed`

> **给代理执行者：** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施本计划。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 严格复刻原型完整链路，在现有 `dashboard` 中补齐“对账阶段”和“模拟盈亏”展示，并保证前后端字段一致、可回放、可测试。

**架构：** 保持现有单页 `dashboard.html` + `routes_dashboard.py` 聚合接口架构不变，仅在运行落库与聚合组装层新增“执行完成/对账结果/盈亏汇总”数据。前端不再推断业务状态，直接按后端返回的时间线事件序列渲染（包含 running/done 双节点）。所有新增行为以 TDD 驱动，并通过 API 合约测试与页面验收测试收敛。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、Alembic、原生 HTML/CSS/JS、pytest

---

## 原型基线来源

- 主基线：`/Users/shenmingjie/Downloads/workbench.html`
- 仓库镜像：`/Users/shenmingjie/workSpace/tranding/a-share-hub/docs/prototype/workbench.html`
- 一致性结论：两份文件内容逐字节一致（`cmp` 返回 `0`），实施与验收按上述原型执行。

---

## 文件结构与职责

- `src/api/routes_dashboard.py`
  - 负责 `POST /api/v1/dashboard/run` 的完整链路拼装（决策 -> 目标仓位 -> 执行 -> 对账）。
  - 负责 `GET /api/v1/dashboard/workbench` 的聚合输出（风险、时间线、历史）。
- `src/storage/runtime_store.py`
  - 负责执行单状态推进（`READY -> FILLED`）与当日模拟盈亏聚合。
- `src/api/dashboard.html`
  - 负责按后端事件序列渲染“running/done 成对节点”。
  - 负责对账节点的文字与盈亏高亮展示。
- `tests/test_dashboard_api.py`
  - 负责 Dashboard API 合约测试（完整链路、仅决策链路、对账与盈亏字段）。
- `tests/test_runtime_store_pg.py`
  - 负责 RuntimeStore 的状态更新与盈亏聚合测试。
- `docs/superpowers/plans/2026-05-26-dashboard-high-fidelity-reconcile-pnl.md`
  - 本计划文档，作为实施与验收依据。

---

## Phase 1：先锁定接口契约（TDD 失败用例）

### 任务 1：补齐 Dashboard 合约测试（先失败）

**文件：**
- 修改：`tests/test_dashboard_api.py`
- 测试：`tests/test_dashboard_api.py`

- [ ] **步骤 1：先写失败测试（完整链路必须出现对账与盈亏）**

```python
def test_run_endpoint_contains_reconcile_stage_and_daily_pnl(test_app):
    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert "daily_pnl" in payload["risk"]
    assert isinstance(payload["risk"]["daily_pnl"], (int, float))

    steps = payload["latest_run"]["steps"]
    assert len(steps) >= 8
    assert [s["stage"] for s in steps][-2:] == ["reconcile", "reconcile"]
    assert steps[-1]["status"] == "done"
    assert "模拟盈亏" in (steps[-1].get("message") or "")
```

- [ ] **步骤 2：再写失败测试（仅决策模式必须跳过执行但保留对账完成节点）**

```python
def test_decision_mode_marks_reconcile_as_skipped(test_app):
    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH"],
            "max_position_ratio": 0.2,
            "execution_mode": "decision",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    steps = payload["latest_run"]["steps"]
    assert steps[-1]["stage"] == "reconcile"
    assert steps[-1]["status"] == "done"
    assert "仅决策模式，跳过执行" in (steps[-1].get("message") or "")
```

- [ ] **步骤 3：运行测试，确认当前失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_contains_reconcile_stage_and_daily_pnl tests/test_dashboard_api.py::test_decision_mode_marks_reconcile_as_skipped -q
```

预期：`FAIL`，提示缺少 `risk.daily_pnl` 或 `latest_run` 未包含 `reconcile` 阶段节点。

- [ ] **步骤 4：提交测试改动**

```bash
git add tests/test_dashboard_api.py
git commit -m "test: define dashboard reconcile and pnl contract"
```

---

## Phase 2：补齐落库与聚合能力（后端）

### 任务 2：在 RuntimeStore 增加执行状态推进与盈亏聚合

**文件：**
- 修改：`src/storage/runtime_store.py`
- 修改：`tests/test_runtime_store_pg.py`
- 测试：`tests/test_runtime_store_pg.py`

- [ ] **步骤 1：先写失败测试（状态推进与当日盈亏）**

```python
def test_runtime_store_can_mark_execution_order_filled_and_sum_daily_pnl(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    order_id = store.insert_execution_order(
        target_position_id="tp-001",
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=100.0,
    )
    store.update_execution_order_status(order_id, status="FILLED")
    store.insert_broker_order_event(
        execution_order_id=order_id,
        event_id="evt-filled-001",
        event_type="FILLED",
        payload={"pnl_delta": 1250.0, "run_context_id": "wrk-test-001"},
    )

    orders = store.list_execution_orders(limit=1)
    assert orders[0]["status"] == "FILLED"
    assert store.sum_daily_pnl() == 1250.0
```

- [ ] **步骤 2：实现最小代码（RuntimeStore）**

```python
def update_execution_order_status(
    self,
    execution_order_id: str,
    status: str,
    broker_order_id: str | None = None,
) -> None:
    values = {"status": status}
    if broker_order_id is not None:
        values["broker_order_id"] = broker_order_id
    with self.engine.begin() as conn:
        conn.execute(
            ExecutionOrderRow.__table__.update()
            .where(ExecutionOrderRow.execution_order_id == execution_order_id)
            .values(**values)
        )


def sum_daily_pnl(self, trade_date: str | None = None) -> float:
    day_prefix = trade_date or datetime.utcnow().date().isoformat()
    total = 0.0
    for event in self.list_broker_events(limit=500):
        if event.get("event_type") != "FILLED":
            continue
        created_at = str(event.get("created_at") or "")
        if not created_at.startswith(day_prefix):
            continue
        payload = event.get("payload") or {}
        try:
            total += float(payload.get("pnl_delta", 0.0))
        except (TypeError, ValueError):
            continue
    return round(total, 2)
```

- [ ] **步骤 3：运行测试，确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py::test_runtime_store_can_mark_execution_order_filled_and_sum_daily_pnl -q
```

预期：`PASS`，并且不影响既有 `test_runtime_store_pg.py` 其他用例。

- [ ] **步骤 4：提交**

```bash
git add src/storage/runtime_store.py tests/test_runtime_store_pg.py
git commit -m "feat: add execution fill transition and daily pnl aggregation"
```

### 任务 3：在 Dashboard run/workbench 中补齐对账阶段与盈亏字段

**文件：**
- 修改：`src/api/routes_dashboard.py`
- 修改：`tests/test_dashboard_api.py`
- 测试：`tests/test_dashboard_api.py`

- [ ] **步骤 1：先写失败测试（时间线顺序必须严格复刻）**

```python
def test_run_endpoint_timeline_sequence_matches_high_fidelity_prototype(test_app):
    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "capital_base": 1_000_000,
            "watchlist": ["600519.SH", "000858.SZ"],
            "max_position_ratio": 0.2,
            "execution_mode": "full",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    steps = payload["latest_run"]["steps"]
    assert [f"{s['stage']}:{s['status']}" for s in steps[:8]] == [
        "decision:running",
        "decision:done",
        "target:running",
        "target:done",
        "execute:running",
        "execute:done",
        "reconcile:running",
        "reconcile:done",
    ]
```

- [ ] **步骤 2：实现最小代码（run 路由）**

```python
def _build_timeline_events_for_run(
    watchlist: list[str],
    decisions: list[dict],
    targets: list[dict],
    orders: list[dict],
    decision_only: bool,
    pnl_value: float,
) -> list[dict]:
    now = datetime.utcnow().isoformat()
    events = [
        {"stage": "decision", "status": "running", "timestamp": now, "message": f"输入标的: {', '.join(watchlist)}"},
        {"stage": "decision", "status": "done", "timestamp": now, "items": decisions},
        {"stage": "target", "status": "running", "timestamp": now, "message": "计算中..."},
        {"stage": "target", "status": "done", "timestamp": now, "items": targets},
    ]
    if decision_only:
        events.append({"stage": "reconcile", "status": "done", "timestamp": now, "message": "仅决策模式，跳过执行"})
        return events
    events.extend(
        [
            {"stage": "execute", "status": "running", "timestamp": now, "message": "发送订单中..."},
            {"stage": "execute", "status": "done", "timestamp": now, "items": orders},
            {"stage": "reconcile", "status": "running", "timestamp": now, "message": "核对执行结果..."},
            {"stage": "reconcile", "status": "done", "timestamp": now, "message": f"所有订单已确认，持仓已更新。模拟盈亏: +¥{pnl_value:,.0f}"},
        ]
    )
    return events
```

- [ ] **步骤 3：实现最小代码（执行与对账数据）**

```python
per_order_pnl = round(1250.0 / max(len(watchlist), 1), 2)
if execution_mode != "decision":
    execution_order_id = store.insert_execution_order(...)
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
        event_type="SUBMITTED",
        payload={"source": "dashboard", "run_context_id": run_context_id},
    )
    store.update_execution_order_status(execution_order_id, status="FILLED")
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
        event_type="FILLED",
        payload={"source": "dashboard", "run_context_id": run_context_id, "pnl_delta": per_order_pnl},
    )
```

- [ ] **步骤 4：实现最小代码（workbench risk 与 latest_run）**

```python
daily_pnl = store.sum_daily_pnl()
risk = {
    "active_target_count": len(targets),
    "open_orders": reconciliation.get("open_orders", 0),
    "broker_event_count": reconciliation.get("broker_event_count", 0),
    "healthy": reconciliation.get("healthy", False),
    "daily_pnl": daily_pnl,
}
```

- [ ] **步骤 5：运行测试，确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py -q
```

预期：`PASS`，新增链路测试通过，旧测试不回归。

- [ ] **步骤 6：提交**

```bash
git add src/api/routes_dashboard.py tests/test_dashboard_api.py
git commit -m "feat: add reconcile stage and pnl contract for dashboard run"
```

---

## Phase 3：前端严格复刻（高保真渲染）

### 任务 4：让 dashboard.html 与新契约一一对齐

**文件：**
- 修改：`src/api/dashboard.html`
- 测试：`tests/test_dashboard_api.py`（接口回归）

- [ ] **步骤 1：先写失败断言（前端渲染规则）**

```python
def test_workbench_payload_provides_reconcile_message_for_frontend_render(test_app):
    client = TestClient(test_app)
    payload = client.post(
        "/api/v1/dashboard/run",
        json={"capital_base": 1_000_000, "watchlist": ["600519.SH"], "max_position_ratio": 0.2, "execution_mode": "full"},
    ).json()
    reconcile_done = [s for s in payload["latest_run"]["steps"] if s["stage"] == "reconcile" and s["status"] == "done"][0]
    assert "模拟盈亏" in reconcile_done["message"]
```

- [ ] **步骤 2：实现最小代码（对账节点样式与盈亏）**

```javascript
function stageBodyHtml(step) {
  const stage = normalizeText(step.stage || step.name, "").toLowerCase();
  if (stage === "reconcile") {
    const message = normalizeText(step.message, "--");
    const pnlMatch = message.match(/([+-]¥[\\d,]+)/);
    if (!pnlMatch) return escapeHtml(message);
    const pnl = pnlMatch[1];
    const safeMessage = escapeHtml(message.replace(pnl, ""));
    return `${safeMessage}<span style="color:var(--green)">${escapeHtml(pnl)}</span>`;
  }
  // 其余分支保持现有逻辑
}
```

- [ ] **步骤 3：实现最小代码（风险卡盈亏与对账一致）**

```javascript
function renderRisk(risk, targets) {
  const pnl = Number(pickFirst(risk, ["daily_pnl", "pnl", "today_pnl"], 0)) || 0;
  const pnlEl = document.getElementById("risk-pnl");
  pnlEl.textContent = formatCurrency(pnl);
  pnlEl.className = `risk-value ${pnl >= 0 ? "green" : "red"}`;
}
```

- [ ] **步骤 4：运行验证**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_workbench_payload_provides_reconcile_message_for_frontend_render -q
```

预期：`PASS`，并且浏览器中运行一轮后出现“对账”节点与“模拟盈亏”文案。

- [ ] **步骤 5：提交**

```bash
git add src/api/dashboard.html tests/test_dashboard_api.py
git commit -m "feat: render reconcile stage and pnl in high-fidelity timeline"
```

---

## Phase 4：联调验收与文档收敛

### 任务 5：端到端验收与文档补充

**文件：**
- 修改：`README.md`
- 测试：`tests/test_dashboard_api.py`、`tests/test_runtime_store_pg.py`、手工 UI 验收

- [ ] **步骤 1：补 README 中 dashboard 验收命令**

```markdown
## Dashboard 验收

```bash
curl -X POST http://127.0.0.1:8010/api/v1/dashboard/run \
  -H 'Content-Type: application/json' \
  -d '{"capital_base":1000000,"watchlist":["600519.SH","000858.SZ"],"max_position_ratio":0.2,"execution_mode":"full"}'
```

预期：`latest_run.steps` 包含 `decision/target/execute/reconcile`，且 `risk.daily_pnl` 为数值。
```

- [ ] **步骤 2：跑完整回归**

```bash
export TEST_DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)"
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py tests/test_dashboard_api.py -q
```

预期：`PASS`，无新增失败。

- [ ] **步骤 3：手工 UI 验收（Chrome）**

```text
1) 打开 http://127.0.0.1:8010/dashboard
2) 点击“运行一轮模拟交易”
3) 中央时间线应按顺序出现：
   决策(running/done) -> 目标仓位(running/done) -> 执行(running/done) -> 对账(running/done)
4) 对账 done 节点包含“模拟盈亏: +¥...”
5) 右侧“当日累计盈亏”与对账文案数值一致
```

- [ ] **步骤 4：提交**

```bash
git add README.md
git commit -m "docs: add dashboard reconcile and pnl acceptance checklist"
```

---

## 分阶段验收标准（必须逐阶段通过）

### Phase 1 验收标准（契约先行）
- `tests/test_dashboard_api.py` 中新增 2 个失败用例，覆盖：
  - `risk.daily_pnl` 字段存在且类型正确。
  - `latest_run.steps` 包含 `reconcile` 阶段，且仅决策模式存在“跳过执行”文案。
- 未完成前禁止进入 Phase 2。

### Phase 2 验收标准（后端真实链路）
- `POST /api/v1/dashboard/run` 返回 `200`。
- Full 模式下 `latest_run.steps` 前 8 个节点顺序固定：
  - `decision:running -> decision:done -> target:running -> target:done -> execute:running -> execute:done -> reconcile:running -> reconcile:done`
- `history.orders[].status` 为 `FILLED`（不再是 `READY`）。
- `risk.daily_pnl` 为可解析数值，`tests/test_runtime_store_pg.py` 与 `tests/test_dashboard_api.py` 全通过。

### Phase 3 验收标准（高保真 UI）
- 中央时间线视觉顺序与图 1 一致，必须出现“对账”阶段。
- 对账完成节点显示“模拟盈亏: +¥N”且为绿色高亮。
- 右侧“当日累计盈亏”与对账完成节点金额一致。
- 仅决策模式下：出现“仅决策模式，跳过执行”，不出现执行表格节点。

### Phase 4 验收标准（联调闭环）
- Chrome Network 中 `run/workbench/kill-switch/status` 全部 `200`。
- 连续运行两轮，页面不出现 `undefined`、不出现 `500`。
- 文档、接口、测试命令与仓库实际入口一致（`/opt/anaconda3/envs/py311/bin/python3 -m src.main serve`）。

---

## 自检结果

- **Spec 覆盖：** 已覆盖“缺少对账阶段”和“缺少盈亏显示”两项核心差异，并落实到后端契约、前端渲染、测试与手工验收。
- **占位词扫描：** 无 `TODO/TBD/implement later` 等占位描述；每个代码步骤均给出具体片段与执行命令。
- **类型一致性：** 统一使用 `risk.daily_pnl`、`latest_run.steps[].stage/status/message/items`，避免同义字段分叉。

---

计划已完成，并保存到 `docs/superpowers/plans/2026-05-26-dashboard-high-fidelity-reconcile-pnl.md`。有两种执行方式：

**1. Subagent-Driven（推荐）** - 我按任务派发新的子代理执行，在任务之间做评审，迭代更快

**2. Inline Execution** - 我在当前会话中使用 `executing-plans` 执行这些任务，按检查点分批推进

**请选择哪一种方式？**
