# Dashboard 功能恢复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复新版模块化仪表板中缺失的核心功能，使其与旧版功能完整对齐

**Architecture:** 在现有模块化架构基础上，扩展 index.html 和 dashboard.js，添加策略配置、风控状态、数据面板等功能。保持模块化设计，每个功能独立封装。

**Tech Stack:** HTML5, CSS3, Vanilla JavaScript, FastAPI

---

## 文件结构

```
src/api/static/
├── index.html                 # 需要扩展：添加策略配置、风控状态等 HTML 结构
├── css/
│   └── dashboard.css          # 需要扩展：添加新功能的样式
└── js/
    ├── app.js                 # 无需修改
    ├── utils.js               # 无需修改
    ├── api.js                 # 需要扩展：添加配置保存、运行模拟等 API
    ├── state.js               # 需要扩展：添加配置状态管理
    └── views/
        ├── dashboard.js       # 需要扩展：添加策略配置、风控状态等渲染逻辑
        ├── market.js          # 无需修改
        └── alpha.js           # 无需修改
```

---

## Task 1: 扩展 index.html 添加缺失的 HTML 结构

**Files:**
- Modify: `src/api/static/index.html`

- [ ] **Step 1: 读取当前 index.html**

```bash
cat src/api/static/index.html | head -50
```

- [ ] **Step 2: 修改状态栏添加状态指示器**

在 `src/api/static/index.html` 中，找到状态栏部分，添加状态指示器：

```html
<!-- Status Bar -->
<div class="status-bar">
  <span class="brand">A股模拟工作台</span>
  <span class="sep"></span>
  <div class="nav-group">
    <button data-view="view-dashboard" onclick="switchView(this, 'view-dashboard')">工作台</button>
    <button data-view="view-market" onclick="switchView(this, 'view-market')">实时行情</button>
    <button data-view="view-alpha" onclick="switchView(this, 'view-alpha')"><i class="bi bi-graph-up"></i> Alpha</button>
  </div>
  <span class="pill mode" id="mode-pill">影子模式</span>
  <span class="sep"></span>
  <span class="pill ok"><span class="dot g" id="db-dot"></span> 数据库</span>
  <span class="pill ok"><span class="dot g" id="llm-dot"></span> LLM</span>
  <span class="pill ok"><span class="dot g" id="mkt-dot"></span> 行情</span>
  <span class="sep"></span>
  <span class="dim" id="trade-date">交易日: --</span>
  <span class="dim" id="last-run">上次运行: --</span>
  <div class="status-right">
    <button id="kill-switch-btn" class="kill-btn" onclick="toggleKillSwitch()">KILL SWITCH</button>
  </div>
</div>
```

- [ ] **Step 3: 修改 Dashboard View 添加策略配置和风控状态**

替换 `#view-dashboard` 内容：

```html
<!-- Dashboard View -->
<div class="view active" id="view-dashboard">
  <div class="main">
    <!-- Left Panel: 策略配置 -->
    <div class="panel-left">
      <h2>策略配置</h2>
      <div class="field">
        <label>模拟总资金 (万元)</label>
        <input type="number" id="cfg-capital" value="100" step="10" min="1">
      </div>
      <div class="field">
        <label>观察列表 (逗号分隔)</label>
        <textarea id="cfg-watchlist" placeholder="600519.SH,000858.SZ,601318.SH">600519.SH,000858.SZ,601318.SH</textarea>
      </div>
      <div class="field">
        <label>手动添加股票</label>
        <input type="text" id="cfg-add-stock" placeholder="输入代码后按回车添加，如 600519.SH">
      </div>
      <div class="field-row">
        <div class="field">
          <label>单票最大仓位 (%)</label>
          <input type="number" id="cfg-max-pos" value="20" min="1" max="100">
        </div>
        <div class="field">
          <label>止损阈值 (%)</label>
          <input type="number" id="cfg-stop-loss" value="-5" step="0.5">
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>单日最大亏损 (%)</label>
          <input type="number" id="cfg-max-daily" value="-3" step="0.5">
        </div>
        <div class="field">
          <label>决策模式</label>
          <select id="cfg-mode">
            <option value="mock">Mock (模拟)</option>
            <option value="real">Real (实盘决策)</option>
          </select>
        </div>
      </div>
      <div class="toggle-row">
        <span>允许新开仓</span>
        <div class="toggle on" id="cfg-new-pos" onclick="this.classList.toggle('on')"></div>
      </div>
      <button class="save-btn" id="save-btn" onclick="savePreferences()">保存配置</button>
      <div id="save-status" style="font-size:11px;color:var(--dim);text-align:center;margin-top:2px"></div>
      <button class="run-btn" id="run-btn" onclick="triggerRun()">运行一轮模拟交易</button>
      <div style="font-size:10px;color:var(--dim);margin-top:4px">
        快捷键: Ctrl+Enter 运行 | Ctrl+S 保存
      </div>
      <h2 style="margin-top:12px;border-top:1px solid var(--border);padding-top:14px">快速回测</h2>
      <div class="field-row">
        <div class="field">
          <label>开始日期</label>
          <input type="date" id="cfg-bt-start">
        </div>
        <div class="field">
          <label>结束日期</label>
          <input type="date" id="cfg-bt-end">
        </div>
      </div>
      <button class="run-btn" id="bt-btn" onclick="triggerBacktest()">运行回测</button>
      <div id="bt-result" style="margin-top:8px;font-size:12px;color:var(--muted)"></div>
    </div>

    <!-- Center Panel: 今日选股 + 本轮运行 -->
    <div class="panel-center">
      <h2>今日选股</h2>
      <div class="scan-card" id="scan-result">
        <button class="run-btn" id="scan-btn" onclick="triggerScan()" style="margin-bottom:10px;font-size:12px;padding:8px 12px">全市场扫描</button>
        <div id="scan-content" style="font-size:12px;color:var(--dim)">点击按钮开始全市场扫描</div>
      </div>

      <h2>本轮运行</h2>
      <div class="timeline" id="timeline">
        <div class="timeline-empty" id="timeline-empty">
          配置参数后点击「运行一轮模拟交易」开始
        </div>
      </div>
    </div>

    <!-- Right Panel: 风控状态 -->
    <div class="panel-right">
      <h2>风控状态</h2>
      <div class="risk-card">
        <div class="risk-label">当日累计盈亏</div>
        <div class="risk-value green" id="risk-pnl">CNY 0</div>
      </div>
      <div class="risk-card">
        <div class="risk-label">持仓集中度</div>
        <div class="risk-value" id="risk-concentration" style="color:var(--fg)">--</div>
      </div>
      <div class="risk-card">
        <div class="risk-label">活跃目标仓位</div>
        <div class="risk-value" id="risk-targets" style="color:var(--accent)">0</div>
      </div>
      <div class="risk-card">
        <div class="risk-label">未完成订单</div>
        <div class="risk-value" id="risk-open-orders" style="color:var(--yellow)">0</div>
      </div>
      <h2>执行模式</h2>
      <div class="mode-switch" id="exec-mode">
        <button class="active" data-mode="full" onclick="setExecMode(this)">完整链路</button>
        <button data-mode="decision" onclick="setExecMode(this)">仅决策</button>
      </div>
      <div id="mode-status" style="font-size:11px;color:var(--dim);margin-top:8px;padding:8px;background:var(--bg);border-radius:6px;line-height:1.6"></div>
      <h2>异常提示</h2>
      <div id="alerts-area">
        <div class="alert-item info">系统就绪，等待运行</div>
      </div>
    </div>

    <!-- Bottom Panel: 数据面板 -->
    <div class="panel-bottom">
      <div class="tab-bar">
        <button class="active" onclick="switchTab(this,'tab-decisions')">最近决策</button>
        <button onclick="switchTab(this,'tab-orders')">最近订单</button>
        <button onclick="switchTab(this,'tab-targets')">当前目标仓位</button>
        <button onclick="switchTab(this,'tab-errors')">异常事件</button>
      </div>
      <div class="tab-content">
        <div class="tab-pane active" id="tab-decisions">
          <table><thead><tr><th>时间</th><th>股票</th><th>动作</th><th>置信度</th><th>理由</th></tr></thead><tbody id="tb-decisions"><tr><td colspan="5" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
        </div>
        <div class="tab-pane" id="tab-orders">
          <table><thead><tr><th>时间</th><th>股票</th><th>方向</th><th>数量</th><th>价格</th><th>状态</th></tr></thead><tbody id="tb-orders"><tr><td colspan="6" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
        </div>
        <div class="tab-pane" id="tab-targets">
          <table><thead><tr><th>股票</th><th>目标仓位</th><th>当前仓位</th><th>差额</th></tr></thead><tbody id="tb-targets"><tr><td colspan="4" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
        </div>
        <div class="tab-pane" id="tab-errors">
          <table><thead><tr><th>时间</th><th>类型</th><th>消息</th></tr></thead><tbody id="tb-errors"><tr><td colspan="3" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
        </div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 4: 提交更改**

```bash
git add src/api/static/index.html
git commit -m "feat: add missing HTML structure for strategy config and risk control"
```

---

## Task 2: 扩展 CSS 添加新功能样式

**Files:**
- Modify: `src/api/static/css/dashboard.css`

- [ ] **Step 1: 读取当前 CSS**

```bash
wc -l src/api/static/css/dashboard.css
```

- [ ] **Step 2: 添加缺失的 CSS 样式**

在 `src/api/static/css/dashboard.css` 末尾添加：

```css
/* ── MAIN LAYOUT ── */
.main{display:grid;grid-template-columns:280px 1fr 280px;grid-template-rows:1fr auto;gap:0;min-height:calc(100vh - 40px)}

/* ── LEFT PANEL ── */
.panel-left{
  background:var(--surface);border-right:1px solid var(--border);padding:16px;overflow-y:auto;
  display:flex;flex-direction:column;gap:14px;
}
.panel-left h2{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.field{display:flex;flex-direction:column;gap:4px}
.field label{font-size:12px;color:var(--dim);font-weight:500}
.field input,.field select,.field textarea{
  background:var(--bg);border:1px solid var(--border);color:var(--fg);
  padding:8px 10px;border-radius:6px;font-size:13px;font-family:inherit;
}
.field input:focus,.field select:focus,.field textarea:focus{outline:none;border-color:var(--accent)}
.field textarea{resize:vertical;min-height:60px}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:6px 0}
.toggle-row span{font-size:13px;color:var(--muted)}
.toggle{
  width:36px;height:20px;background:var(--border);border-radius:10px;position:relative;cursor:pointer;transition:.2s;
}
.toggle.on{background:var(--green)}
.toggle::after{
  content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;
  background:#fff;border-radius:50%;transition:.2s;
}
.toggle.on::after{left:18px}
.run-btn{
  background:var(--blue);color:#fff;border:none;padding:12px;border-radius:8px;
  font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;transition:.15s;
}
.run-btn:hover{background:#2563eb}
.run-btn:disabled{opacity:.5;cursor:not-allowed}
.save-btn{
  background:var(--green);border:none;color:#fff;
  padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;
  cursor:pointer;transition:.15s;width:100%;margin-top:4px;
}
.save-btn:hover{background:#16a34a}
.save-btn:active{transform:scale(.97)}

/* ── CENTER PANEL ── */
.panel-center{padding:16px;overflow-y:auto;display:flex;flex-direction:column;gap:12px}
.panel-center h2{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.timeline{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:16px;flex:1;overflow-y:auto;min-height:300px;
}
.timeline-empty{
  display:flex;align-items:center;justify-content:center;height:100%;
  color:var(--dim);font-size:14px;
}
.tl-step{
  border-left:2px solid var(--border);padding:0 0 16px 16px;position:relative;
}
.tl-step:last-child{border-left-color:transparent;padding-bottom:0}
.tl-step::before{
  content:'';position:absolute;left:-6px;top:2px;width:10px;height:10px;
  border-radius:50%;background:var(--border);border:2px solid var(--bg);
}
.tl-step.done::before{background:var(--green)}
.tl-step.running::before{background:var(--yellow);animation:pulse 1s infinite}
.tl-step.error::before{background:var(--red)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.tl-step .step-head{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.tl-step .step-tag{
  font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase;
}
.tl-step .step-tag.decision{background:rgba(96,165,250,.2);color:var(--accent)}
.tl-step .step-tag.target{background:rgba(34,197,94,.15);color:var(--green)}
.tl-step .step-tag.execute{background:rgba(234,179,8,.15);color:var(--yellow)}
.tl-step .step-tag.reconcile{background:rgba(139,92,246,.2);color:#a78bfa}
.tl-step .step-time{font-size:11px;color:var(--dim)}
.tl-step .step-body{font-size:13px;color:var(--muted);line-height:1.6}
.tl-step .step-body table{width:100%;border-collapse:collapse;margin-top:6px}
.tl-step .step-body th,.tl-step .step-body td{
  padding:4px 8px;text-align:left;border-bottom:1px solid var(--border);font-size:12px;
}
.tl-step .step-body th{color:var(--dim);font-weight:500;font-size:11px;text-transform:uppercase}
.tl-step pre{
  background:var(--bg);padding:8px;border-radius:6px;font-size:12px;
  overflow-x:auto;color:var(--fg);margin-top:6px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}

/* ── RIGHT PANEL ── */
.panel-right{
  background:var(--surface);border-left:1px solid var(--border);padding:16px;overflow-y:auto;
  display:flex;flex-direction:column;gap:14px;
}
.panel-right h2{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.risk-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:12px}
.risk-card .risk-label{font-size:11px;color:var(--dim);text-transform:uppercase;margin-bottom:4px}
.risk-card .risk-value{font-size:20px;font-weight:700}
.risk-card .risk-value.green{color:var(--green)}.risk-card .risk-value.red{color:var(--red)}.risk-card .risk-value.yellow{color:var(--yellow)}
.alert-item{
  padding:8px 10px;border-radius:6px;font-size:12px;margin-bottom:6px;
  border-left:3px solid;display:flex;align-items:flex-start;gap:6px;
}
.alert-item.warn{background:rgba(234,179,8,.08);border-color:var(--yellow);color:var(--yellow)}
.alert-item.err{background:rgba(239,68,68,.08);border-color:var(--red);color:var(--red)}
.alert-item.info{background:rgba(96,165,250,.08);border-color:var(--accent);color:var(--accent)}
.mode-switch{display:flex;gap:4px;background:var(--bg);border-radius:6px;padding:3px}
.mode-switch button{
  flex:1;padding:6px 8px;border:none;border-radius:4px;font-size:12px;
  font-weight:600;cursor:pointer;background:transparent;color:var(--muted);transition:.15s;
}
.mode-switch button.active{background:var(--blue);color:#fff}

/* ── BOTTOM PANEL ── */
.panel-bottom{
  grid-column:1/-1;background:var(--surface);border-top:1px solid var(--border);
  padding:0 20px;height:280px;min-height:200px;display:flex;flex-direction:column;
}
.tab-bar{display:flex;gap:0;border-bottom:1px solid var(--border)}
.tab-bar button{
  padding:10px 18px;border:none;background:transparent;color:var(--muted);
  font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:.15s;
}
.tab-bar button.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab-content{flex:1;overflow-y:auto;padding:12px 0}
.tab-pane{display:none}.tab-pane.active{display:block}
.tab-pane table{width:100%;border-collapse:collapse}
.tab-pane th,.tab-pane td{
  padding:8px 12px;text-align:left;border-bottom:1px solid var(--border);font-size:12px;
}
.tab-pane th{color:var(--dim);font-weight:500;text-transform:uppercase}
```

- [ ] **Step 3: 提交更改**

```bash
git add src/api/static/css/dashboard.css
git commit -m "feat: add CSS styles for strategy config and risk control panels"
```

---

## Task 3: 扩展 API 添加配置保存和运行模拟功能

**Files:**
- Modify: `src/api/static/js/api.js`

- [ ] **Step 1: 读取当前 api.js**

```bash
cat src/api/static/js/api.js
```

- [ ] **Step 2: 添加新的 API 端点**

在 `src/api/static/js/api.js` 末尾添加：

```javascript
// 配置保存 API
const CONFIG_API = '/api/v1/dashboard/config';
const RUN_API = '/api/v1/dashboard/run';
const BACKTEST_API = '/api/v1/dashboard/backtest';
const SCAN_API = '/api/v1/dashboard/scan';

// 保存配置
async function saveConfig(config) {
  const response = await fetch(CONFIG_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return await parseResponseBody(response);
}

// 运行模拟
async function runSimulation() {
  const response = await fetch(RUN_API, { method: 'POST' });
  return await parseResponseBody(response);
}

// 运行回测
async function runBacktest(startDate, endDate) {
  const response = await fetch(BACKTEST_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_date: startDate, end_date: endDate })
  });
  return await parseResponseBody(response);
}

// 运行扫描
async function runScan() {
  const response = await fetch(SCAN_API, { method: 'POST' });
  return await parseResponseBody(response);
}
```

- [ ] **Step 3: 提交更改**

```bash
git add src/api/static/js/api.js
git commit -m "feat: add API functions for config save, simulation, backtest, and scan"
```

---

## Task 4: 扩展 State 添加配置状态管理

**Files:**
- Modify: `src/api/static/js/state.js`

- [ ] **Step 1: 读取当前 state.js**

```bash
cat src/api/static/js/state.js
```

- [ ] **Step 2: 添加配置状态**

在 `src/api/static/js/state.js` 末尾添加：

```javascript
// 配置状态
const ConfigState = {
  capital: 100,
  watchlist: ['600519.SH', '000858.SZ', '601318.SH'],
  maxPosition: 20,
  stopLoss: -5,
  maxDailyLoss: -3,
  mode: 'mock',
  allowNewPosition: true,
  execMode: 'full'
};

// 更新配置
function updateConfig(key, value) {
  ConfigState[key] = value;
  console.log(`Config updated: ${key} = ${value}`);
}

// 获取配置
function getConfig() {
  return { ...ConfigState };
}

// 从表单同步配置
function syncConfigFromForm() {
  ConfigState.capital = parseInt(document.getElementById('cfg-capital')?.value || '100');
  ConfigState.watchlist = (document.getElementById('cfg-watchlist')?.value || '').split(',').filter(s => s.trim());
  ConfigState.maxPosition = parseInt(document.getElementById('cfg-max-pos')?.value || '20');
  ConfigState.stopLoss = parseFloat(document.getElementById('cfg-stop-loss')?.value || '-5');
  ConfigState.maxDailyLoss = parseFloat(document.getElementById('cfg-max-daily')?.value || '-3');
  ConfigState.mode = document.getElementById('cfg-mode')?.value || 'mock';
  ConfigState.allowNewPosition = document.getElementById('cfg-new-pos')?.classList.contains('on') ?? true;
}
```

- [ ] **Step 3: 提交更改**

```bash
git add src/api/static/js/state.js
git commit -m "feat: add configuration state management"
```

---

## Task 5: 扩展 dashboard.js 添加策略配置渲染逻辑

**Files:**
- Modify: `src/api/static/js/views/dashboard.js`

- [ ] **Step 1: 读取当前 dashboard.js**

```bash
wc -l src/api/static/js/views/dashboard.js
```

- [ ] **Step 2: 添加策略配置渲染函数**

在 `src/api/static/js/views/dashboard.js` 末尾添加：

```javascript
// 渲染策略配置
function renderConfig(config) {
  if (!config || configHydrated) return;
  configHydrated = true;
  
  const modeEl = document.getElementById('cfg-mode');
  if (modeEl) modeEl.value = config.mode || 'mock';
  
  const capitalEl = document.getElementById('cfg-capital');
  if (capitalEl) capitalEl.value = config.capital || 100;
  
  const watchlistEl = document.getElementById('cfg-watchlist');
  if (watchlistEl) watchlistEl.value = (config.watchlist || []).join(',');
  
  const maxPosEl = document.getElementById('cfg-max-pos');
  if (maxPosEl) maxPosEl.value = config.maxPosition || 20;
  
  const stopLossEl = document.getElementById('cfg-stop-loss');
  if (stopLossEl) stopLossEl.value = config.stopLoss || -5;
  
  const maxDailyEl = document.getElementById('cfg-max-daily');
  if (maxDailyEl) maxDailyEl.value = config.maxDailyLoss || -3;
  
  const newPosEl = document.getElementById('cfg-new-pos');
  if (newPosEl) {
    if (config.allowNewPosition) {
      newPosEl.classList.add('on');
    } else {
      newPosEl.classList.remove('on');
    }
  }
  
  updateModeStatus();
}

// 渲染风控状态
function renderRisk(risk, targets) {
  const pnlEl = document.getElementById('risk-pnl');
  if (pnlEl) pnlEl.textContent = `CNY ${risk.daily_pnl || 0}`;
  
  const concentrationEl = document.getElementById('risk-concentration');
  if (concentrationEl) concentrationEl.textContent = risk.concentration || '--';
  
  const targetsEl = document.getElementById('risk-targets');
  if (targetsEl) targetsEl.textContent = risk.active_target_count || targets.length || 0;
  
  const openOrdersEl = document.getElementById('risk-open-orders');
  if (openOrdersEl) openOrdersEl.textContent = risk.open_orders || 0;
}

// 渲染异常提示
function renderAlerts(alerts) {
  const alertsArea = document.getElementById('alerts-area');
  if (!alertsArea) return;
  
  if (!alerts || alerts.length === 0) {
    alertsArea.innerHTML = '<div class="alert-item info">系统就绪，等待运行</div>';
    return;
  }
  
  alertsArea.innerHTML = alerts.map(alert => {
    const type = alert.level || 'info';
    return `<div class="alert-item ${type}">${alert.message || alert}</div>`;
  }).join('');
}

// 渲染数据面板
function renderDataPanel(data) {
  renderDecisions(data.history?.decisions || []);
  renderOrders(data.history?.orders || []);
  renderTargets(data.history?.targets || []);
  renderErrorEvents(data.history?.events || []);
}

// 渲染最近决策
function renderDecisions(list) {
  const tbody = document.getElementById('tb-decisions');
  if (!tbody) return;
  
  if (!list || list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = list.map(d => `
    <tr>
      <td>${formatTime(d.timestamp)}</td>
      <td>${d.symbol || '--'}</td>
      <td>${d.action || '--'}</td>
      <td>${d.confidence ? (d.confidence * 100).toFixed(0) + '%' : '--'}</td>
      <td>${truncateText(d.reason || '--', 50)}</td>
    </tr>
  `).join('');
}

// 渲染最近订单
function renderOrders(list) {
  const tbody = document.getElementById('tb-orders');
  if (!tbody) return;
  
  if (!list || list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = list.map(o => `
    <tr>
      <td>${formatTime(o.timestamp)}</td>
      <td>${o.symbol || '--'}</td>
      <td>${o.side || '--'}</td>
      <td>${o.quantity || '--'}</td>
      <td>${o.price || '--'}</td>
      <td>${o.status || '--'}</td>
    </tr>
  `).join('');
}

// 渲染当前目标仓位
function renderTargets(list) {
  const tbody = document.getElementById('tb-targets');
  if (!tbody) return;
  
  if (!list || list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = list.map(t => `
    <tr>
      <td>${t.symbol || '--'}</td>
      <td>${t.target_position || '--'}</td>
      <td>${t.current_position || '--'}</td>
      <td>${t.diff || '--'}</td>
    </tr>
  `).join('');
}

// 渲染异常事件
function renderErrorEvents(list) {
  const tbody = document.getElementById('tb-errors');
  if (!tbody) return;
  
  if (!list || list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = list.map(e => `
    <tr>
      <td>${formatTime(e.timestamp)}</td>
      <td>${e.type || '--'}</td>
      <td>${truncateText(e.message || '--', 80)}</td>
    </tr>
  `).join('');
}

// 渲染时间线
function renderTimeline(run) {
  const timeline = document.getElementById('timeline');
  const timelineEmpty = document.getElementById('timeline-empty');
  
  if (!timeline) return;
  
  if (!run || !run.steps || run.steps.length === 0) {
    if (timelineEmpty) timelineEmpty.style.display = 'flex';
    return;
  }
  
  if (timelineEmpty) timelineEmpty.style.display = 'none';
  
  timeline.innerHTML = run.steps.map(step => `
    <div class="tl-step ${step.status || 'running'}">
      <div class="step-head">
        <span class="step-tag ${step.type || 'decision'}">${step.type || 'step'}</span>
        <span class="step-time">${formatTime(step.timestamp)}</span>
      </div>
      <div class="step-body">${step.description || step.message || ''}</div>
    </div>
  `).join('');
}

// 保存配置
async function savePreferences() {
  syncConfigFromForm();
  const config = getConfig();
  
  try {
    const result = await saveConfig(config);
    const saveStatus = document.getElementById('save-status');
    if (saveStatus) {
      saveStatus.textContent = '配置已保存';
      saveStatus.style.color = 'var(--green)';
      setTimeout(() => { saveStatus.textContent = ''; }, 3000);
    }
  } catch (error) {
    addAlert('err', `保存配置失败: ${error.message}`);
  }
}

// 运行模拟
async function triggerRun() {
  const runBtn = document.getElementById('run-btn');
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.textContent = '运行中...';
  }
  
  try {
    await runSimulation();
    addAlert('info', '模拟运行已启动');
    setTimeout(loadDashboard, 2000);
  } catch (error) {
    addAlert('err', `运行失败: ${error.message}`);
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.textContent = '运行一轮模拟交易';
    }
  }
}

// 运行回测
async function triggerBacktest() {
  const startDate = document.getElementById('cfg-bt-start')?.value;
  const endDate = document.getElementById('cfg-bt-end')?.value;
  
  if (!startDate || !endDate) {
    addAlert('warn', '请选择回测日期范围');
    return;
  }
  
  const btBtn = document.getElementById('bt-btn');
  if (btBtn) {
    btBtn.disabled = true;
    btBtn.textContent = '回测中...';
  }
  
  try {
    const result = await runBacktest(startDate, endDate);
    const btResult = document.getElementById('bt-result');
    if (btResult) {
      btResult.textContent = `回测完成: ${result.message || '成功'}`;
    }
  } catch (error) {
    addAlert('err', `回测失败: ${error.message}`);
  } finally {
    if (btBtn) {
      btBtn.disabled = false;
      btBtn.textContent = '运行回测';
    }
  }
}

// 运行扫描
async function triggerScan() {
  const scanBtn = document.getElementById('scan-btn');
  const scanContent = document.getElementById('scan-content');
  
  if (scanBtn) {
    scanBtn.disabled = true;
    scanBtn.textContent = '扫描中...';
  }
  
  if (scanContent) {
    scanContent.textContent = '正在扫描全市场...';
  }
  
  try {
    const result = await runScan();
    if (scanContent) {
      scanContent.textContent = `扫描完成: ${result.stocks?.length || 0} 只股票`;
    }
  } catch (error) {
    if (scanContent) {
      scanContent.textContent = `扫描失败: ${error.message}`;
    }
  } finally {
    if (scanBtn) {
      scanBtn.disabled = false;
      scanBtn.textContent = '全市场扫描';
    }
  }
}

// Tab 切换
function switchTab(btn, tabId) {
  // 移除所有 active 类
  document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  
  // 添加 active 类
  btn.classList.add('active');
  const tabPane = document.getElementById(tabId);
  if (tabPane) tabPane.classList.add('active');
}

// 执行模式切换
function setExecMode(btn) {
  document.querySelectorAll('#exec-mode button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  
  const mode = btn.dataset.mode;
  updateModeStatus(mode);
}

// 更新模式状态显示
function updateModeStatus(execMode) {
  const modeStatus = document.getElementById('mode-status');
  if (!modeStatus) return;
  
  const configMode = document.getElementById('cfg-mode')?.value || 'mock';
  const allowNew = document.getElementById('cfg-new-pos')?.classList.contains('on');
  
  modeStatus.innerHTML = `
    决策: <strong>${configMode === 'mock' ? 'Mock (模拟)' : 'Real (实盘)'}</strong> | 
    执行: <strong>${execMode === 'full' ? '完整链路' : '仅决策'}</strong> | 
    新开仓: <strong>${allowNew ? '是' : '否'}</strong><br>
    ▶️ 决策 → 目标仓位 → 执行 → 对账
  `;
}

// 快捷键处理
document.addEventListener('keydown', function(e) {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    triggerRun();
  }
  if (e.ctrlKey && e.key === 's') {
    e.preventDefault();
    savePreferences();
  }
});

// 添加股票到观察列表
document.addEventListener('DOMContentLoaded', function() {
  const addStockInput = document.getElementById('cfg-add-stock');
  if (addStockInput) {
    addStockInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const stockCode = this.value.trim();
        if (stockCode) {
          const watchlistEl = document.getElementById('cfg-watchlist');
          if (watchlistEl) {
            const current = watchlistEl.value;
            watchlistEl.value = current ? `${current},${stockCode}` : stockCode;
            this.value = '';
          }
        }
      }
    });
  }
});
```

- [ ] **Step 3: 提交更改**

```bash
git add src/api/static/js/views/dashboard.js
git commit -m "feat: add strategy config and risk control rendering functions"
```

---

## Task 6: 验证所有功能

**Files:**
- Test: 所有修改的文件

- [ ] **Step 1: 重启服务器**

```bash
pkill -f "src.main serve" 2>/dev/null
sleep 1
nohup /opt/anaconda3/envs/py311/bin/python3 -m src.main serve > /tmp/a-share-hub.log 2>&1 &
sleep 3
```

- [ ] **Step 2: 测试新版本**

```bash
curl -s http://127.0.0.1:8000/static/index.html | grep -c "策略配置"
curl -s http://127.0.0.1:8000/static/index.html | grep -c "风控状态"
curl -s http://127.0.0.1:8000/static/index.html | grep -c "最近决策"
```

- [ ] **Step 3: 使用 Playwright 测试**

```bash
playwright-cli open http://localhost:8000/static/index.html --browser=chrome
playwright-cli screenshot --filename=/tmp/playwright-screenshots/new-dashboard-restored.png
playwright-cli close
```

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: complete dashboard feature restoration"
```

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-01-dashboard-feature-restoration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 我为每个任务派发一个子代理，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中执行任务，批量执行并设置检查点

**选择哪种方式？**
