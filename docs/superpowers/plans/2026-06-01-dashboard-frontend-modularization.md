# Dashboard Frontend Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic `src/api/dashboard.html` (2034 lines) into modular JavaScript files while keeping the pure HTML/CSS/JS stack. FastAPI serves all static files directly.

**Architecture:** SPA with hash routing (`#/dashboard`, `#/market`, `#/alpha`). Each view is a separate JS file exporting `init()` and `render()` functions. Shared utilities extracted to `utils.js`, API calls wrapped in `api.js`, global state in `state.js`.

**Tech Stack:** HTML, CSS, JavaScript (ES6+), FastAPI StaticFiles

---

## File Structure

```
src/api/static/
├── index.html                 # SPA entry (~100 lines)
├── css/
│   └── dashboard.css          # All styles (~400 lines)
└── js/
    ├── app.js                 # Route management (~80 lines)
    ├── utils.js               # Pure utility functions (~100 lines)
    ├── api.js                 # API fetch wrapper (~80 lines)
    ├── state.js               # Global state (~50 lines)
    └── views/
        ├── dashboard.js       # Workbench view (~300 lines)
        ├── market.js          # Market view (~300 lines)
        └── alpha.js           # Alpha view (~200 lines)
```

---

### Task 1: Create Directory Structure and Extract CSS

**Files:**
- Create: `src/api/static/css/dashboard.css`
- Create: `src/api/static/js/views/` (empty directory)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/api/static/css
mkdir -p src/api/static/js/views
```

- [ ] **Step 2: Extract CSS from dashboard.html**

Read `src/api/dashboard.html` lines 1-175 (the `<style>` block) and write to `src/api/static/css/dashboard.css`.

The CSS file should contain all styles from `<style>` to `</style>`.

- [ ] **Step 3: Verify CSS file exists**

```bash
ls -la src/api/static/css/dashboard.css
wc -l src/api/static/css/dashboard.css
```

Expected: File exists with ~400 lines

- [ ] **Step 4: Commit**

```bash
git add src/api/static/
git commit -m "feat: create static directory and extract CSS"
```

---

### Task 2: Extract Utils.js (Pure Functions)

**Files:**
- Create: `src/api/static/js/utils.js`

- [ ] **Step 1: Extract utility functions from dashboard.html**

Read `src/api/dashboard.html` and extract these functions to `src/api/static/js/utils.js`:

```javascript
// src/api/static/js/utils.js

function normalizeText(value, fallback = '--') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function pickFirst(obj, keys, fallback = null) {
  for (const key of keys) {
    if (obj && obj[key] !== null && obj[key] !== undefined && obj[key] !== '') {
      return obj[key];
    }
  }
  return fallback;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDate(raw) {
  const value = normalizeText(raw, '');
  if (!value) return '--';
  return value.includes('T') ? value.split('T')[0] : value.slice(0, 10);
}

function formatTime(raw) {
  const value = normalizeText(raw, '');
  if (!value) return '--';
  if (value.includes('T')) {
    const time = value.split('T')[1] || '';
    return time.split('.')[0] || '--';
  }
  if (value.includes(' ')) {
    return value.split(' ')[1] || value;
  }
  return value.length > 8 ? value.slice(0, 8) : value;
}

function formatPercent(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return `${(n * 100).toFixed(1)}%`;
}

function formatConfidence(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const pct = n <= 1 ? n * 100 : n;
  return `${pct.toFixed(0)}%`;
}

function formatCurrency(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return n.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' });
}

function formatNumber(raw, digits = 2) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return n.toFixed(digits);
}

function formatSignedPercent(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const pct = (n * 100).toFixed(1);
  return n >= 0 ? `+${pct}%` : `${pct}%`;
}

function formatVolume(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
  return n.toFixed(0);
}

function toList(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined) return [];
  return [value];
}

function serviceDotClass(status) {
  if (status === 'ok' || status === 'running') return 'dot-green';
  if (status === 'error' || status === 'stopped') return 'dot-red';
  return 'dot-yellow';
}

function toAlertLevel(level) {
  if (level === 'critical' || level === 'error') return 'error';
  if (level === 'warning') return 'warning';
  return 'info';
}

function extractErrorMessage(body, fallback) {
  if (typeof body === 'string') return body;
  if (body && body.detail) return body.detail;
  if (body && body.message) return body.message;
  return fallback;
}
```

- [ ] **Step 2: Verify utils.js exists**

```bash
ls -la src/api/static/js/utils.js
wc -l src/api/static/js/utils.js
```

Expected: File exists with ~100 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/utils.js
git commit -m "feat: extract utils.js with pure functions"
```

---

### Task 3: Extract API.js (Fetch Wrapper)

**Files:**
- Create: `src/api/static/js/api.js`

- [ ] **Step 1: Create API wrapper**

```javascript
// src/api/static/js/api.js

const API_BASE = '/api/v1';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}

const AlphaAPI = {
  getAssets:       ()         => apiFetch('/alpha/assets'),
  getTickets:      ()         => apiFetch('/alpha/tickets'),
  createTicket:    (data)     => apiFetch('/alpha/tickets', { method: 'POST', body: JSON.stringify(data) }),
  approveTicket:   (id)       => apiFetch(`/alpha/tickets/${id}/approve`, { method: 'POST' }),
  createFill:      (id, data) => apiFetch(`/alpha/tickets/${id}/fills`, { method: 'POST', body: JSON.stringify(data) }),
  getCapabilities: ()         => apiFetch('/alpha/capabilities'),
  getWorkbench:    ()         => apiFetch('/dashboard/workbench'),
  getWatchlist:    ()         => apiFetch('/alpha/watchlist'),
  addWatchlist:    (data)     => apiFetch('/alpha/watchlist', { method: 'POST', body: JSON.stringify(data) }),
  scanResearch:    ()         => apiFetch('/alpha/research/scan', { method: 'POST' }),
  proposeTicket:   (data)     => apiFetch('/alpha/research/propose-top-ticket', { method: 'POST', body: JSON.stringify(data) }),
};

const MarketAPI = {
  getQuote:    (symbol) => apiFetch(`/market/quote/${symbol}`),
  getBulk:     (symbols) => apiFetch('/market/bulk', { method: 'POST', body: JSON.stringify({ symbols }) }),
  search:      (query) => apiFetch(`/market/search?q=${encodeURIComponent(query)}`),
};

const DashboardAPI = {
  getWorkbench:    ()         => apiFetch('/dashboard/workbench'),
  runDecision:     (payload)  => apiFetch('/dashboard/run', { method: 'POST', body: JSON.stringify(payload) }),
  getKillSwitch:   ()         => apiFetch('/kill-switch/status'),
  activateKill:    ()         => apiFetch('/kill-switch/activate', { method: 'POST' }),
  deactivateKill:  ()         => apiFetch('/kill-switch/deactivate', { method: 'POST' }),
};
```

- [ ] **Step 2: Verify api.js exists**

```bash
ls -la src/api/static/js/api.js
wc -l src/api/static/js/api.js
```

Expected: File exists with ~80 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/api.js
git commit -m "feat: extract api.js with fetch wrapper"
```

---

### Task 4: Extract State.js (Global State)

**Files:**
- Create: `src/api/static/js/state.js`

- [ ] **Step 1: Create state management**

```javascript
// src/api/static/js/state.js

const State = {
  execMode: 'full',
  killSwitch: false,
  configHydrated: false,
  simRunning: false,
  pagination: {
    decisions: { page: 0, data: [] },
    orders:    { page: 0, data: [] },
    targets:   { page: 0, data: [] },
    errors:    { page: 0, data: [] },
  },
  PAGE_SIZE: 10,
};

function pagSlice(key) {
  const p = State.pagination[key];
  const start = p.page * State.PAGE_SIZE;
  return p.data.slice(start, start + State.PAGE_SIZE);
}

function pagTotal(key) {
  return Math.max(1, Math.ceil(State.pagination[key].data.length / State.PAGE_SIZE));
}

function pagPrev(key) {
  if (State.pagination[key].page > 0) {
    State.pagination[key].page--;
    renderPagTab(key);
  }
}

function pagNext(key) {
  if (State.pagination[key].page < pagTotal(key) - 1) {
    State.pagination[key].page++;
    renderPagTab(key);
  }
}

function renderPagControls(key) {
  const total = pagTotal(key);
  const cur = State.pagination[key].page + 1;
  return `<div class="pagination">
    <button onclick="pagPrev('${key}')" ${cur <= 1 ? 'disabled' : ''}>上一页</button>
    <span class="page-info">${cur} / ${total}</span>
    <button onclick="pagNext('${key}')" ${cur >= total ? 'disabled' : ''}>下一页</button>
  </div>`;
}

function renderPagTab(key) {
  const renderers = {
    decisions: renderDecisions,
    orders: renderOrders,
    targets: renderTargets,
    errors: renderErrorEvents,
  };
  if (renderers[key]) renderers[key](State.pagination[key].data);
}
```

- [ ] **Step 2: Verify state.js exists**

```bash
ls -la src/api/static/js/state.js
wc -l src/api/static/js/state.js
```

Expected: File exists with ~50 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/state.js
git commit -m "feat: extract state.js with global state"
```

---

### Task 5: Extract Alpha View (alpha.js)

**Files:**
- Create: `src/api/static/js/views/alpha.js`

- [ ] **Step 1: Create alpha view module**

```javascript
// src/api/static/js/views/alpha.js

function initAlpha() {
  // Bind events
  const ticketForm = document.getElementById('alpha-ticket-form');
  if (ticketForm) {
    ticketForm.addEventListener('submit', submitAlphaTicket);
  }
}

function renderAlpha() {
  loadAlphaAssets();
  loadAlphaTickets();
  loadAlphaWatchlist();
  loadAlphaCapabilities();
}

async function loadAlphaAssets() {
  const root = document.getElementById('alpha-assets');
  if (!root) return;
  try {
    const data = await AlphaAPI.getAssets();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无资产数据</span>';
      return;
    }
    root.innerHTML = data.items.map(asset => `
      <div class="asset-row">
        <strong>${escapeHtml(asset.symbol)}</strong>
        <span>${escapeHtml(asset.underlying_symbol)}</span>
        <span>${escapeHtml(asset.market_status)}</span>
        <span>${escapeHtml(asset.asset_status)}</span>
      </div>
    `).join('');
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

async function loadAlphaTickets() {
  const root = document.getElementById('alpha-tickets');
  if (!root) return;
  try {
    const data = await AlphaAPI.getTickets();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无建议单</span>';
      return;
    }
    renderAlphaTickets(data.items);
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  if (!root) return;
  root.innerHTML = items.map(item => `
    <div class="ticket-row">
      <strong>${escapeHtml(item.asset_symbol)}</strong>
      <span>${escapeHtml(item.action)}</span>
      <span>${escapeHtml(String(item.suggested_quantity))}</span>
      <span>@ ${escapeHtml(String(item.suggested_limit_price))}</span>
      <span>${escapeHtml(item.status)}</span>
    </div>
  `).join('');
}

async function submitAlphaTicket(event) {
  event.preventDefault();
  const btn = event.target.querySelector('button[type="submit"]');
  setButtonLoading(btn, true, '创建建议单');
  try {
    const payload = {
      asset_symbol: document.getElementById('alpha-symbol').value.trim(),
      underlying_symbol: document.getElementById('alpha-underlying').value.trim(),
      action: 'BUY',
      thesis: document.getElementById('alpha-thesis').value.trim(),
      suggested_quantity: Number(document.getElementById('alpha-qty').value),
      suggested_limit_price: Number(document.getElementById('alpha-limit').value),
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    };
    await AlphaAPI.createTicket(payload);
    showToast('建议单已创建', 'success');
    loadAlphaTickets();
    event.target.reset();
  } catch (err) {
    showToast('创建失败: ' + err.message, 'error');
  } finally {
    setButtonLoading(btn, false, '创建建议单');
  }
}

async function loadAlphaWatchlist() {
  const root = document.getElementById('alpha-watchlist');
  if (!root) return;
  try {
    const data = await AlphaAPI.getWatchlist();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无观察标的</span>';
      return;
    }
    renderAlphaWatchlist(data.items);
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

function renderAlphaWatchlist(items) {
  const root = document.getElementById('alpha-watchlist');
  if (!root) return;
  root.innerHTML = items.map(item => `
    <div class="watchlist-row">
      <strong>${escapeHtml(item.symbol)}</strong>
      <span>${escapeHtml(item.underlying_symbol)}</span>
      <span>优先级: ${item.priority}</span>
    </div>
  `).join('');
}

async function loadAlphaCapabilities() {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  if (!modeEl || !reasonEl) return;
  try {
    const data = await AlphaAPI.getCapabilities();
    renderAlphaExecutionCapability(data);
  } catch (err) {
    modeEl.textContent = '未知';
    reasonEl.textContent = '获取失败';
  }
}

function renderAlphaExecutionCapability(capability) {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  if (modeEl) modeEl.textContent = capability.mode || '未知';
  if (reasonEl) reasonEl.textContent = capability.reason || '';
}

async function runAlphaScan() {
  const root = document.getElementById('alpha-candidates');
  if (!root) return;
  root.innerHTML = '<span class="loading-spinner"></span> 扫描中...';
  try {
    const data = await AlphaAPI.scanResearch();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">无候选结果</span>';
      return;
    }
    root.innerHTML = data.items.map(item => `
      <div class="candidate-row">
        <strong>${escapeHtml(item.symbol)}</strong>
        <span>${escapeHtml(item.action)}</span>
        <span>评分: ${formatNumber(item.score, 4)}</span>
        <span>${escapeHtml(item.reason)}</span>
      </div>
    `).join('');
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">扫描失败</span>';
  }
}

async function proposeTopAlphaTicket() {
  try {
    const data = await AlphaAPI.proposeTicket({ thesis_prefix: 'dashboard auto' });
    showToast('建议单已生成: ' + data.asset_symbol, 'success');
    loadAlphaTickets();
  } catch (err) {
    showToast('生成失败: ' + err.message, 'error');
  }
}
```

- [ ] **Step 2: Verify alpha.js exists**

```bash
ls -la src/api/static/js/views/alpha.js
wc -l src/api/static/js/views/alpha.js
```

Expected: File exists with ~200 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/views/alpha.js
git commit -m "feat: extract alpha.js view module"
```

---

### Task 6: Extract Dashboard View (dashboard.js)

**Files:**
- Create: `src/api/static/js/views/dashboard.js`

- [ ] **Step 1: Create dashboard view module**

```javascript
// src/api/static/js/views/dashboard.js

function initDashboard() {
  // Bind events for dashboard view
}

function renderDashboard() {
  loadWorkbench();
}

async function loadWorkbench() {
  try {
    const [workbench, killStatus] = await Promise.all([
      DashboardAPI.getWorkbench(),
      DashboardAPI.getKillSwitch(),
    ]);
    renderWorkbench(workbench, killStatus);
  } catch (err) {
    showToast('加载工作台失败: ' + err.message, 'error');
  }
}

function renderWorkbench(data, killStatus) {
  renderStatus(data, killStatus);
  renderConfig(data.config);
  renderDecisions(data.decisions || []);
  renderOrders(data.orders || []);
  renderTargets(data.targets || []);
  renderRisk(data.risk, data.targets);
  renderErrorEvents(data.errors || []);
  renderAlerts(data.alerts || []);
  renderTimeline(data.latest_run);
}

function renderStatus(workbench, killStatus) {
  const statusEl = document.getElementById('service-status');
  if (!statusEl) return;
  const services = workbench.services || {};
  statusEl.innerHTML = Object.entries(services).map(([name, status]) => `
    <span class="service-dot ${serviceDotClass(status)}"></span>
    <span>${escapeHtml(name)}</span>
  `).join('');
  setKillSwitchButton(killStatus.active);
}

function setKillSwitchButton(active) {
  State.killSwitch = active;
  const btn = document.getElementById('kill-switch-btn');
  if (!btn) return;
  btn.textContent = active ? '解除风控' : '触发风控';
  btn.className = active ? 'btn-danger active' : 'btn-danger';
}

function renderConfig(config) {
  if (!config || State.configHydrated) return;
  State.configHydrated = true;
  const modeEl = document.getElementById('cfg-mode');
  if (modeEl) modeEl.value = config.mode || 'mock';
  updateModeStatus();
}

function renderDecisions(list) {
  State.pagination.decisions.data = list;
  const root = document.getElementById('decisions-pane');
  if (!root) return;
  const items = pagSlice('decisions');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>标的</th><th>决策</th><th>置信度</th></tr></thead>
      <tbody>${items.map(d => `
        <tr>
          <td>${formatTime(d.created_at)}</td>
          <td>${escapeHtml(d.symbol)}</td>
          <td>${escapeHtml(d.action)}</td>
          <td>${formatConfidence(d.confidence)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('decisions')}
  ` : '<span style="color:var(--dim)">暂无决策记录</span>';
}

function renderOrders(list) {
  State.pagination.orders.data = list;
  const root = document.getElementById('orders-pane');
  if (!root) return;
  const items = pagSlice('orders');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>标的</th><th>方向</th><th>数量</th><th>状态</th></tr></thead>
      <tbody>${items.map(o => `
        <tr>
          <td>${formatTime(o.created_at)}</td>
          <td>${escapeHtml(o.symbol)}</td>
          <td>${escapeHtml(o.side)}</td>
          <td>${formatNumber(o.quantity)}</td>
          <td>${escapeHtml(o.status)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('orders')}
  ` : '<span style="color:var(--dim)">暂无订单记录</span>';
}

function renderTargets(list) {
  State.pagination.targets.data = list;
  const root = document.getElementById('targets-pane');
  if (!root) return;
  const items = pagSlice('targets');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>标的</th><th>目标持仓</th><th>当前持仓</th><th>漂移</th></tr></thead>
      <tbody>${items.map(t => `
        <tr>
          <td>${escapeHtml(t.symbol)}</td>
          <td>${formatNumber(t.target_quantity)}</td>
          <td>${formatNumber(t.current_quantity)}</td>
          <td>${formatSignedPercent(t.drift)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('targets')}
  ` : '<span style="color:var(--dim)">暂无目标仓位</span>';
}

function renderRisk(risk, targets) {
  const root = document.getElementById('risk-summary');
  if (!root || !risk) return;
  root.innerHTML = `
    <div class="bt-card">
      <div class="bt-row"><span class="bt-label">总市值</span><span class="bt-value">${formatCurrency(risk.total_value)}</span></div>
      <div class="bt-row"><span class="bt-label">持仓数</span><span class="bt-value">${targets ? targets.length : 0}</span></div>
      <div class="bt-row"><span class="bt-label">现金</span><span class="bt-value">${formatCurrency(risk.cash)}</span></div>
    </div>
  `;
}

function renderErrorEvents(events) {
  State.pagination.errors.data = events;
  const root = document.getElementById('errors-pane');
  if (!root) return;
  const items = pagSlice('errors');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>级别</th><th>消息</th></tr></thead>
      <tbody>${items.map(e => `
        <tr>
          <td>${formatTime(e.created_at)}</td>
          <td><span class="badge badge-${toAlertLevel(e.level)}">${escapeHtml(e.level)}</span></td>
          <td>${escapeHtml(e.message)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('errors')}
  ` : '<span style="color:var(--dim)">暂无错误事件</span>';
}

function renderAlerts(alerts) {
  const root = document.getElementById('alerts-pane');
  if (!root) return;
  if (!alerts || alerts.length === 0) {
    root.innerHTML = '<span style="color:var(--dim)">暂无告警</span>';
    return;
  }
  root.innerHTML = alerts.map(a => `
    <div class="alert-item alert-${toAlertLevel(a.level)}">
      <span class="alert-time">${formatTime(a.created_at)}</span>
      <span class="alert-msg">${escapeHtml(a.message)}</span>
    </div>
  `).join('');
}

function renderTimeline(latestRun) {
  const root = document.getElementById('timeline-pane');
  if (!root || !latestRun) return;
  const steps = latestRun.steps || [];
  root.innerHTML = `
    <div class="timeline">
      ${steps.map(step => `
        <div class="timeline-step ${step.status === 'completed' ? 'completed' : ''}">
          <div class="timeline-dot"></div>
          <div class="timeline-content">
            <strong>${escapeHtml(step.name)}</strong>
            <span>${formatTime(step.completed_at)}</span>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function stageLabel(stage) {
  const labels = {
    'input': '输入构建',
    'decision': '决策生成',
    'target': '目标规划',
    'execution': '订单执行',
    'reconciliation': '对账检查',
  };
  return labels[stage] || stage;
}

function stageBodyHtml(step) {
  if (!step.details) return '';
  return `<pre>${escapeHtml(JSON.stringify(step.details, null, 2))}</pre>`;
}
```

- [ ] **Step 2: Verify dashboard.js exists**

```bash
ls -la src/api/static/js/views/dashboard.js
wc -l src/api/static/js/views/dashboard.js
```

Expected: File exists with ~300 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/views/dashboard.js
git commit -m "feat: extract dashboard.js view module"
```

---

### Task 7: Extract Market View (market.js)

**Files:**
- Create: `src/api/static/js/views/market.js`

- [ ] **Step 1: Create market view module**

```javascript
// src/api/static/js/views/market.js

let searchMode = false;
let searchResults = [];

function initMarket() {
  const searchInput = document.getElementById('market-search');
  if (searchInput) {
    searchInput.addEventListener('keydown', handleSearchKeydown);
  }
}

function renderMarket() {
  refreshMarketQuotes();
}

async function refreshMarketQuotes() {
  const symbols = buildQuoteSymbols();
  if (symbols.length === 0) return;
  try {
    const data = await MarketAPI.getBulk(symbols);
    renderMarketQuotes(data);
  } catch (err) {
    showToast('获取行情失败: ' + err.message, 'error');
  }
}

function buildQuoteSymbols() {
  const watchlist = State.watchlist || [];
  return watchlist.map(w => w.symbol).filter(Boolean);
}

function renderMarketQuotes(quotes) {
  const root = document.getElementById('market-quotes');
  if (!root) return;
  if (!quotes || quotes.length === 0) {
    root.innerHTML = '<span style="color:var(--dim)">暂无行情数据</span>';
    return;
  }
  root.innerHTML = `
    <table class="scan-table">
      <thead>
        <tr>
          <th>代码</th>
          <th>最新价</th>
          <th>涨跌幅</th>
          <th>成交量</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        ${quotes.map(q => `
          <tr>
            <td><strong>${escapeHtml(q.symbol)}</strong></td>
            <td>${formatNumber(q.price)}</td>
            <td class="${q.change >= 0 ? 'quote-up' : 'quote-down'}">${formatSignedPercent(q.change)}</td>
            <td>${formatVolume(q.volume)}</td>
            <td>
              <button onclick="addToWatchlist('${escapeHtml(q.symbol)}')" class="btn-sm">加自选</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function handleSearchKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    const query = event.target.value.trim();
    if (query) {
      await performSearch(query);
    }
  }
}

async function performSearch(query) {
  searchMode = true;
  try {
    const data = await MarketAPI.search(query);
    searchResults = data.items || [];
    renderSearchResults();
  } catch (err) {
    showToast('搜索失败: ' + err.message, 'error');
  }
}

function renderSearchResults() {
  const root = document.getElementById('search-results');
  if (!root) return;
  if (searchResults.length === 0) {
    root.innerHTML = '<span style="color:var(--dim)">无搜索结果</span>';
    return;
  }
  root.innerHTML = searchResults.map((item, index) => `
    <div class="search-result-item" onclick="selectSearchResult(${index})">
      <strong>${escapeHtml(item.symbol)}</strong>
      <span>${escapeHtml(item.name)}</span>
      <span class="badge badge-${item.market_status === 'TRADING' ? 'buy' : 'hold'}">${escapeHtml(item.market_status)}</span>
    </div>
  `).join('');
}

function selectSearchResult(index) {
  const item = searchResults[index];
  if (!item) return;
  showToast(`已选择: ${item.symbol}`, 'info');
}

async function addToWatchlist(symbol) {
  try {
    await MarketAPI.addWatchlist({ symbol });
    showToast(`已添加 ${symbol} 到自选`, 'success');
    refreshMarketQuotes();
  } catch (err) {
    showToast('添加失败: ' + err.message, 'error');
  }
}
```

- [ ] **Step 2: Verify market.js exists**

```bash
ls -la src/api/static/js/views/market.js
wc -l src/api/static/js/views/market.js
```

Expected: File exists with ~300 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/views/market.js
git commit -m "feat: extract market.js view module"
```

---

### Task 8: Create App.js (Route Management)

**Files:**
- Create: `src/api/static/js/app.js`

- [ ] **Step 1: Create app entry point**

```javascript
// src/api/static/js/app.js

const routes = {
  '#/dashboard': { init: initDashboard, render: renderDashboard },
  '#/market':    { init: initMarket,    render: renderMarket },
  '#/alpha':     { init: initAlpha,     render: renderAlpha },
};

let initialized = {};

function navigateTo(hash) {
  const route = routes[hash] || routes['#/dashboard'];
  const viewId = hash.replace('#/', 'view-');

  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

  // Show target view
  const view = document.getElementById(viewId);
  if (view) view.classList.add('active');

  // Update nav buttons
  document.querySelectorAll('.nav-group button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });

  // Initialize if first time
  if (!initialized[hash]) {
    initialized[hash] = true;
    route.init();
  }

  // Render view
  route.render();

  // Update URL
  window.location.hash = hash;
}

function switchView(btn, viewId) {
  const hash = '#/' + viewId.replace('view-', '');
  navigateTo(hash);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash || '#/dashboard';
  navigateTo(hash);
});

// Listen for hash changes
window.addEventListener('hashchange', () => {
  navigateTo(window.location.hash);
});
```

- [ ] **Step 2: Verify app.js exists**

```bash
ls -la src/api/static/js/app.js
wc -l src/api/static/js/app.js
```

Expected: File exists with ~80 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/js/app.js
git commit -m "feat: create app.js route management"
```

---

### Task 9: Create index.html (SPA Entry)

**Files:**
- Create: `src/api/static/index.html`

- [ ] **Step 1: Create HTML skeleton**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A股模拟工作台</title>
  <link rel="stylesheet" href="/static/css/dashboard.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
</head>
<body>

<!-- Status Bar -->
<div class="status-bar">
  <span class="brand">A股模拟工作台</span>
  <span class="sep"></span>
  <div class="nav-group">
    <button data-view="view-dashboard" onclick="switchView(this, 'view-dashboard')">工作台</button>
    <button data-view="view-market" onclick="switchView(this, 'view-market')">实时行情</button>
    <button data-view="view-alpha" onclick="switchView(this, 'view-alpha')"><i class="bi bi-graph-up"></i> Alpha</button>
  </div>
  <div class="status-right">
    <span id="service-status"></span>
    <button id="kill-switch-btn" class="btn-danger" onclick="toggleKillSwitch()">触发风控</button>
  </div>
</div>

<!-- Dashboard View -->
<div class="view active" id="view-dashboard">
  <div class="main">
    <div class="card">
      <h3>决策记录</h3>
      <div id="decisions-pane"></div>
    </div>
    <div class="card">
      <h3>订单记录</h3>
      <div id="orders-pane"></div>
    </div>
    <div class="card">
      <h3>目标仓位</h3>
      <div id="targets-pane"></div>
    </div>
    <div class="card">
      <h3>风险摘要</h3>
      <div id="risk-summary"></div>
    </div>
    <div class="card">
      <h3>错误事件</h3>
      <div id="errors-pane"></div>
    </div>
    <div class="card">
      <h3>告警</h3>
      <div id="alerts-pane"></div>
    </div>
    <div class="card">
      <h3>执行时间线</h3>
      <div id="timeline-pane"></div>
    </div>
    <div class="card">
      <h3>配置</h3>
      <div id="config-pane">
        <label>决策模式</label>
        <select id="cfg-mode" onchange="updateModeStatus()">
          <option value="mock">Mock (模拟)</option>
          <option value="real">Real (实盘)</option>
        </select>
        <div id="mode-status"></div>
      </div>
    </div>
  </div>
</div>

<!-- Market View -->
<div class="view" id="view-market">
  <div class="search-bar">
    <input id="market-search" type="text" placeholder="搜索代码或名称...">
  </div>
  <div id="search-results"></div>
  <div id="market-quotes"></div>
</div>

<!-- Alpha View -->
<div class="view" id="view-alpha">
  <h2>Alpha 代币化证券</h2>
  <div class="risk-card" id="alpha-execution-capability">
    <div class="risk-label">Direct Execution Capability</div>
    <div id="alpha-execution-mode"></div>
    <div id="alpha-execution-reason"></div>
  </div>
  <div class="risk-card">
    <div class="risk-label">资产状态</div>
    <div id="alpha-assets"></div>
  </div>
  <div class="risk-card">
    <div class="risk-label">建议单</div>
    <form id="alpha-ticket-form">
      <input id="alpha-symbol" placeholder="资产代码 (如 AAPLx)" />
      <input id="alpha-underlying" placeholder="标的代码 (如 AAPL)" />
      <input id="alpha-qty" type="number" placeholder="数量" />
      <input id="alpha-limit" type="number" step="0.01" placeholder="限价" />
      <textarea id="alpha-thesis" placeholder="投资逻辑"></textarea>
      <button type="submit">创建建议单</button>
    </form>
    <div id="alpha-tickets"></div>
  </div>
  <div class="risk-card">
    <div class="risk-label">观察列表与候选</div>
    <button onclick="runAlphaScan()">运行扫描</button>
    <button onclick="proposeTopAlphaTicket()">生成建议单</button>
    <div id="alpha-watchlist"></div>
    <div id="alpha-candidates"></div>
  </div>
</div>

<!-- Toast Container -->
<div id="toast-container"></div>

<!-- Scripts -->
<script src="/static/js/utils.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/state.js"></script>
<script src="/static/js/views/dashboard.js"></script>
<script src="/static/js/views/market.js"></script>
<script src="/static/js/views/alpha.js"></script>
<script src="/static/js/app.js"></script>

</body>
</html>
```

- [ ] **Step 2: Verify index.html exists**

```bash
ls -la src/api/static/index.html
wc -l src/api/static/index.html
```

Expected: File exists with ~100 lines

- [ ] **Step 3: Commit**

```bash
git add src/api/static/index.html
git commit -m "feat: create index.html SPA entry"
```

---

### Task 10: Configure FastAPI Static Files

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: Add static file serving**

Read `src/api/routes_dashboard.py` and add the following at the end of the file:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/new")
def new_dashboard():
    """Redirect to new modular dashboard"""
    return RedirectResponse(url="/static/index.html")
```

- [ ] **Step 2: Verify FastAPI starts**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve &
sleep 2
curl -s http://127.0.0.1:8000/new | head -c 200
kill %1
```

Expected: HTML content from index.html

- [ ] **Step 3: Commit**

```bash
git add src/api/routes_dashboard.py
git commit -m "feat: configure FastAPI static file serving"
```

---

### Task 11: Verify All Views Work

**Files:** None (manual testing)

- [ ] **Step 1: Start the server**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

- [ ] **Step 2: Test Dashboard view**

Open browser to `http://localhost:8000/new#/dashboard`

Verify:
- Decision records display
- Order records display
- Target positions display
- Risk summary displays
- Error events display
- Alerts display
- Timeline displays
- Config section works

- [ ] **Step 3: Test Market view**

Click "实时行情" button

Verify:
- Search bar works
- Quote table displays
- Add to watchlist works

- [ ] **Step 4: Test Alpha view**

Click "Alpha" button

Verify:
- Assets list displays
- Tickets list displays
- Create ticket form works
- Watchlist displays
- Scan button works
- Propose ticket button works
- Capability panel displays

- [ ] **Step 5: Test route switching**

Click between views multiple times

Verify:
- No flicker
- Data refreshes correctly
- URL hash updates

- [ ] **Step 6: Test error handling**

Disconnect network or use invalid API

Verify:
- Toast notifications appear
- Error messages display correctly

- [ ] **Step 7: Commit final state**

```bash
git add -A
git commit -m "feat: complete dashboard frontend modularization"
```

---

## Summary

This plan splits the monolithic dashboard.html into 9 modular files:

1. `dashboard.css` - All styles
2. `utils.js` - Pure utility functions
3. `api.js` - API fetch wrapper
4. `state.js` - Global state management
5. `dashboard.js` - Workbench view
6. `market.js` - Market view
7. `alpha.js` - Alpha view
8. `app.js` - Route management
9. `index.html` - SPA entry point

Each file has a single responsibility and can be understood independently. The original dashboard.html remains as a backup at `/dashboard`, while the new modular version is available at `/new`.
