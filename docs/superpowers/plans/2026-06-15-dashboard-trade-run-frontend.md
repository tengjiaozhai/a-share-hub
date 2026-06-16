# Dashboard Trade Run Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the dashboard UI so trade runs render progressively, show stock-level reconciliation, and present one consistent run PnL summary.

**Architecture:** Preserve the existing terminal-style dashboard layout and keep the browser as a thin consumer of backend data. Replace the blocking `fetch('/api/v1/dashboard/run')` interaction with a run-start request plus `EventSource` stream, add explicit reconcile and run-summary surfaces, and render the backend’s new `run_pnl_summary`, `reconcile_items`, and stage-duration data without client-side business inference.

**Tech Stack:** Vanilla HTML, CSS, JavaScript, FastAPI inline page rendering, pytest

---

## Scope Check

This plan is frontend-only. It covers the page contract, DOM structure, JavaScript event handling, visual presentation, and browser-facing acceptance tests. It does not define database schema or run-orchestration internals.

## File Structure

- Create: `src/api/dashboard_page/scripts/dashboard_run.js`
  Own the run-start request, SSE subscription, stream-state lifecycle, and incremental timeline updates.
- Modify: `src/api/dashboard_page/render.py`
  Inline the new run-stream script into the rendered page.
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
  Add the run-trace header, stream-state indicator, reconcile tab, and run-summary slots.
- Modify: `src/api/dashboard_page/scripts/dashboard.js`
  Keep shared dashboard rendering, but consume the new stream-aware payload shape and render `run_pnl_summary` and `reconcile_items`.
- Modify: `src/api/dashboard_page/styles/dashboard.css`
  Style the new summary strip, stream-state label, reconcile table, and dense trace cells.
- Modify: `tests/test_dashboard_page_contract.py`
  Lock the DOM contract and embedded JavaScript markers for the new UI path.

### Task 1: Add The DOM Contract For Trace, Stream State, And Reconcile

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write the failing page-contract test**

```python
# tests/test_dashboard_page_contract.py
def test_render_dashboard_html_contains_streaming_run_markers():
    html = render_dashboard_html()
    required_markers = [
        'id="run-trace-id"',
        'id="stream-status"',
        'id="run-pnl-net"',
        'id="run-pnl-fee"',
        'id="run-pnl-unrealized"',
        'id="tab-reconcile"',
        'id="tb-reconcile"',
    ]
    for marker in required_markers:
        assert marker in html
```

- [ ] **Step 2: Run the page-contract test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_streaming_run_markers -v
```

Expected: FAIL because the current page has no run trace, no stream-state label, and no reconcile tab.

- [ ] **Step 3: Add the new DOM anchors**

```html
<!-- src/api/dashboard_page/partials/view_dashboard.html -->
<h2>执行模式</h2>
<div class="mode-switch" id="exec-mode">
  <button class="active" data-mode="full" onclick="setExecMode(this)">完整链路</button>
  <button data-mode="decision" onclick="setExecMode(this)">仅决策</button>
</div>
<div id="mode-status" class="mode-status-box"></div>
<div class="run-meta-strip">
  <span class="run-meta-label">本轮链路</span>
  <span id="run-trace-id" class="run-meta-value">--</span>
  <span id="stream-status" class="stream-pill idle">等待运行</span>
</div>
<div class="run-pnl-strip" aria-label="本轮盈亏摘要">
  <div class="run-pnl-card">
    <span class="run-pnl-label">本轮净影响</span>
    <span class="run-pnl-value" id="run-pnl-net">--</span>
  </div>
  <div class="run-pnl-card">
    <span class="run-pnl-label">执行成本</span>
    <span class="run-pnl-value" id="run-pnl-fee">--</span>
  </div>
  <div class="run-pnl-card">
    <span class="run-pnl-label">持仓浮盈亏</span>
    <span class="run-pnl-value" id="run-pnl-unrealized">--</span>
  </div>
</div>
```

```html
<!-- src/api/dashboard_page/partials/view_dashboard.html -->
<div class="tab-bar">
  <button class="active" onclick="switchTab(this,'tab-decisions')">决策</button>
  <button onclick="switchTab(this,'tab-orders')">订单</button>
  <button onclick="switchTab(this,'tab-targets')">目标仓位</button>
  <button onclick="switchTab(this,'tab-reconcile')">对账</button>
  <button onclick="switchTab(this,'tab-errors')">异常</button>
</div>
<div class="tab-content">
  <div class="tab-pane" id="tab-reconcile">
    <table>
      <thead>
        <tr>
          <th>股票</th>
          <th>数量</th>
          <th>成本价</th>
          <th>现价</th>
          <th>涨跌幅</th>
          <th>未实现盈亏</th>
          <th>手续费</th>
          <th>行情时间</th>
        </tr>
      </thead>
      <tbody id="tb-reconcile">
        <tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>
      </tbody>
    </table>
  </div>
</div>
```

- [ ] **Step 4: Run the page-contract test to verify it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_streaming_run_markers -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard_page/partials/view_dashboard.html tests/test_dashboard_page_contract.py
git commit -m "feat: add dashboard run trace and reconcile dom contract"
```

### Task 2: Replace The Blocking Run Button With Start-Run And EventSource

**Files:**
- Create: `src/api/dashboard_page/scripts/dashboard_run.js`
- Modify: `src/api/dashboard_page/render.py`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write the failing page-contract test for the new client path**

```python
# tests/test_dashboard_page_contract.py
def test_render_dashboard_html_contains_streaming_run_javascript_contract():
    html = render_dashboard_html()
    assert "const RUNS_API = '/api/v1/dashboard/runs';" in html
    assert "const RUN_EVENTS_API = (runContextId) =>" in html
    assert "new EventSource" in html
    assert "connectRunStream" in html
```

- [ ] **Step 2: Run the page-contract test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_streaming_run_javascript_contract -v
```

Expected: FAIL because the current page still embeds `const RUN_API = '/api/v1/dashboard/run';` and has no `EventSource`.

- [ ] **Step 3: Add the new run controller script and wire it into the page**

```python
# src/api/dashboard_page/render.py
def render_dashboard_html(theme_id: str = "trading-terminal") -> str:
    html = _read("shell.html")
    replacements = {
        "{{INLINE_STYLES}}": _read("styles/dashboard.css"),
        "{{STATUS_BAR}}": _read("partials/status_bar.html"),
        "{{VIEW_DASHBOARD}}": _read("partials/view_dashboard.html"),
        "{{VIEW_MARKET}}": _read("partials/view_market.html"),
        "{{VIEW_ALPHA}}": _read("partials/view_alpha.html"),
        "{{INLINE_UTILS_JS}}": _read("scripts/utils.js"),
        "{{INLINE_THEME_JS}}": _read("scripts/theme.js"),
        "{{INLINE_DASHBOARD_JS}}": _read("scripts/dashboard.js"),
        "{{INLINE_DASHBOARD_RUN_JS}}": _read("scripts/dashboard_run.js"),
        "{{INLINE_MARKET_JS}}": _read("scripts/market.js"),
        "{{INLINE_ALPHA_JS}}": _read("scripts/alpha.js"),
        "{{VIEW_US_STOCK}}": _read("partials/view_us_stock.html"),
        "{{INLINE_US_STOCK_JS}}": _read("scripts/us_stock.js"),
        "{{INLINE_BOOTSTRAP_JS}}": _read("scripts/bootstrap.js"),
    }
    for marker, content in replacements.items():
        html = html.replace(marker, content)
    return html.replace("{{THEME_ID}}", theme_id)
```

```javascript
// src/api/dashboard_page/scripts/dashboard_run.js
const RUNS_API = '/api/v1/dashboard/runs';
const RUN_EVENTS_API = (runContextId) => `/api/v1/dashboard/runs/${encodeURIComponent(runContextId)}/events`;

let runEventSource = null;
let currentRunContextId = null;

function setStreamStatus(kind, message) {
  const el = document.getElementById('stream-status');
  if (!el) return;
  el.className = `stream-pill ${kind}`;
  el.textContent = message;
}

function connectRunStream(runContextId) {
  if (runEventSource) {
    runEventSource.close();
    runEventSource = null;
  }
  currentRunContextId = runContextId;
  document.getElementById('run-trace-id').textContent = runContextId;
  setStreamStatus('running', '运行中');
  runEventSource = new EventSource(RUN_EVENTS_API(runContextId));
  runEventSource.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    applyRunStreamEvent(payload);
  };
  runEventSource.addEventListener('run.completed', async (event) => {
    const payload = JSON.parse(event.data);
    await loadRunSnapshot(payload.run_context_id);
    setStreamStatus('success', '本轮完成');
    runEventSource.close();
    runEventSource = null;
    finishRun();
  });
  runEventSource.addEventListener('run.failed', async (event) => {
    const payload = JSON.parse(event.data);
    await loadRunSnapshot(payload.run_context_id);
    setStreamStatus('error', '运行失败');
    addAlert('err', payload.payload?.message || '运行失败');
    runEventSource.close();
    runEventSource = null;
    finishRun();
  });
}

async function loadRunSnapshot(runContextId) {
  const res = await fetch(`${WORKBENCH_API}?run_context_id=${encodeURIComponent(runContextId)}`);
  const body = await parseResponseBody(res);
  if (!res.ok) {
    throw new Error(extractErrorMessage(body, `加载运行快照失败 (${res.status})`));
  }
  renderWorkbench(body, { active: killSwitchActive });
}

async function triggerRun() {
  if (simRunning) return;
  simRunning = true;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, true, '运行中');
  setStreamStatus('pending', '请求中');
  renderTimeline({
    run_context_id: '--',
    steps: [
      {
        stage: 'decision',
        status: 'running',
        timestamp: new Date().toISOString(),
        message: '请求已提交，等待后台接受本轮任务。',
      },
    ],
  });

  try {
    const res = await fetch(RUNS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildRunPayload()),
    });
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, `启动失败 (${res.status})`));
    }
    connectRunStream(body.run_context_id);
  } catch (error) {
    setStreamStatus('error', '启动失败');
    addAlert('err', `运行失败: ${error.message}`);
    finishRun();
  }
}
```

```javascript
// src/api/dashboard_page/scripts/dashboard.js
function finishRun() {
  simRunning = false;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, false, '运行一轮模拟交易');
}
```

- [ ] **Step 4: Run the page-contract test to verify it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_streaming_run_javascript_contract -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard_page/render.py src/api/dashboard_page/scripts/dashboard_run.js src/api/dashboard_page/scripts/dashboard.js tests/test_dashboard_page_contract.py
git commit -m "feat: stream dashboard runs with eventsource"
```

### Task 3: Render Unified Run PnL, Reconcile Rows, And Stage Durations

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write the failing page-contract test for the new renderer hooks**

```python
# tests/test_dashboard_page_contract.py
def test_render_dashboard_html_contains_reconcile_renderer_hooks():
    html = render_dashboard_html()
    assert "renderReconcile(" in html
    assert "renderRunPnlSummary(" in html
    assert "duration_ms" in html
```

- [ ] **Step 2: Run the page-contract test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_reconcile_renderer_hooks -v
```

Expected: FAIL because `dashboard.js` has no reconcile renderer and no unified run-PnL renderer.

- [ ] **Step 3: Implement the renderers and styles**

```javascript
// src/api/dashboard_page/scripts/dashboard.js
function renderRunPnlSummary(summary) {
  const pnl = summary || {};
  const net = Number(pnl.net_pnl || 0);
  const fee = Number(pnl.execution_fee_total || 0);
  const unrealized = Number(pnl.unrealized_pnl || 0);

  const netEl = document.getElementById('run-pnl-net');
  const feeEl = document.getElementById('run-pnl-fee');
  const unrealizedEl = document.getElementById('run-pnl-unrealized');

  if (netEl) {
    netEl.textContent = formatCurrency(net);
    netEl.className = `run-pnl-value ${net > 0 ? 'green' : net < 0 ? 'red' : ''}`;
  }
  if (feeEl) {
    feeEl.textContent = formatCurrency(fee);
    feeEl.className = 'run-pnl-value red';
  }
  if (unrealizedEl) {
    unrealizedEl.textContent = formatCurrency(unrealized);
    unrealizedEl.className = `run-pnl-value ${unrealized > 0 ? 'green' : unrealized < 0 ? 'red' : ''}`;
  }
}

function renderReconcile(list) {
  const rows = toList(list);
  const tb = document.getElementById('tb-reconcile');
  if (!tb) return;
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  tb.innerHTML = rows.map(item => {
    const symbol = normalizeText(item.symbol);
    const quantity = normalizeText(item.quantity);
    const avgCost = formatCurrency(item.avg_cost);
    const markPrice = formatCurrency(item.mark_price);
    const change = formatPercent(item.change_pct);
    const pnl = formatCurrency(item.unrealized_pnl);
    const fee = formatCurrency(item.fee_total);
    const markTime = formatTime(item.mark_time);
    const pnlClass = Number(item.unrealized_pnl) > 0 ? 'green' : Number(item.unrealized_pnl) < 0 ? 'red' : '';
    return `<tr><td>${escapeHtml(symbol)}</td><td>${escapeHtml(quantity)}</td><td>${escapeHtml(avgCost)}</td><td>${escapeHtml(markPrice)}</td><td>${escapeHtml(change)}</td><td class="${pnlClass}">${escapeHtml(pnl)}</td><td>${escapeHtml(fee)}</td><td>${escapeHtml(markTime)}</td></tr>`;
  }).join('');
}

function stageBodyHtml(step) {
  const stage = normalizeText(step.stage || step.name, '').toLowerCase();
  const items = toList(step.items);
  if (stage === 'reconcile' && items.length) {
    const rows = items.map(item => {
      return `<tr><td>${escapeHtml(normalizeText(item.symbol))}</td><td>${escapeHtml(formatCurrency(item.avg_cost))}</td><td>${escapeHtml(formatCurrency(item.mark_price))}</td><td>${escapeHtml(formatPercent(item.change_pct))}</td><td>${escapeHtml(formatCurrency(item.unrealized_pnl))}</td></tr>`;
    }).join('');
    return `<table><tr><th>股票</th><th>成本价</th><th>现价</th><th>涨跌幅</th><th>未实现盈亏</th></tr>${rows}</table>`;
  }
  return legacyStageBodyHtml(step);
}

const legacyStageBodyHtml = stageBodyHtml;

function renderTimeline(latestRun) {
  const timeline = document.getElementById('timeline');
  const steps = toList(latestRun?.steps);
  if (!steps.length) {
    timeline.innerHTML = '<div class="timeline-empty" id="timeline-empty">配置参数后点击「运行一轮模拟交易」开始</div>';
    return;
  }
  timeline.innerHTML = '';
  document.getElementById('run-trace-id').textContent = latestRun?.run_context_id || '--';
  steps.forEach(step => {
    const stage = normalizeText(step.stage || step.name, 'stage').toLowerCase();
    const status = normalizeText(step.status, 'done').toLowerCase();
    const time = formatTime(step.finished_at || step.timestamp || step.created_at);
    const duration = step.duration_ms != null ? ` · ${step.duration_ms}ms` : '';
    const div = document.createElement('div');
    div.className = `tl-step ${status}`;
    div.innerHTML = `
      <div class="step-head">
        <span class="step-tag ${stage}">${escapeHtml(stageLabel(stage))}</span>
        <span class="step-time">${escapeHtml(`${time}${duration}`)}</span>
      </div>
      <div class="step-body">${stageBodyHtml(step)}</div>
    `;
    timeline.appendChild(div);
  });
}

function renderWorkbench(data, killStatus) {
  renderStatus(data, killStatus || {});
  const mergedConfig = Object.assign({}, data.config || {}, data._serverPrefs || {});
  renderConfig(mergedConfig);
  renderDecisions(data.history?.decisions || []);
  renderOrders(data.history?.orders || []);
  renderTargets(data.history?.targets || []);
  renderReconcile(data.history?.reconcile || data.latest_run?.reconcile_items || []);
  renderRunPnlSummary(data.latest_run?.run_pnl_summary || {});
  renderRisk(data.risk || {}, data.history?.targets || []);
  renderAlerts(data.risk?.alerts || []);
  renderTimeline(data.latest_run || { steps: [] });
}
```

```css
/* src/api/dashboard_page/styles/dashboard.css */
.run-meta-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.run-meta-label {
  color: var(--dim);
  font-size: 11px;
}

.run-meta-value {
  color: var(--text);
  font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
}

.stream-pill {
  margin-left: auto;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.stream-pill.idle {
  background: rgba(148, 163, 184, 0.14);
  color: var(--dim);
}

.stream-pill.pending,
.stream-pill.running {
  background: rgba(234, 179, 8, 0.14);
  color: var(--yellow);
}

.stream-pill.success {
  background: rgba(34, 197, 94, 0.14);
  color: var(--green);
}

.stream-pill.error {
  background: rgba(239, 68, 68, 0.14);
  color: var(--red);
}

.run-pnl-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.run-pnl-card {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.run-pnl-label {
  display: block;
  color: var(--dim);
  font-size: 11px;
  margin-bottom: 4px;
}

.run-pnl-value {
  display: block;
  font-size: 14px;
  font-weight: 700;
}
```

- [ ] **Step 4: Run the page-contract test to verify it passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_reconcile_renderer_hooks -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/styles/dashboard.css tests/test_dashboard_page_contract.py
git commit -m "feat: render reconcile rows and unified run pnl summary"
```

## Self-Review

**Spec coverage**

- 对账没有结果: Task 1 adds the reconcile tab and Task 3 renders `reconcile_items`.
- 只有手续费、没有解释当日盈亏: Task 1 adds dedicated run-PnL slots and Task 3 renders `run_pnl_summary`.
- 为什么不是流式输出: Task 2 replaces the blocking run interaction with `EventSource`.
- 需要可见 run 链路: Task 1 adds `run-trace-id` and Task 3 renders stage durations.

**Placeholder scan**

- No placeholder markers remain.
- Every code-changing step includes concrete code and exact commands.

**Type consistency**

- Canonical start endpoint: `RUNS_API`
- Canonical stream endpoint helper: `RUN_EVENTS_API`
- Canonical final summary renderer: `renderRunPnlSummary`
- Canonical reconcile renderer: `renderReconcile`
- Canonical trace DOM ids: `run-trace-id`, `stream-status`, `run-pnl-net`, `run-pnl-fee`, `run-pnl-unrealized`
