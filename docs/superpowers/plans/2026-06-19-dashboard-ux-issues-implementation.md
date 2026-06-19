# Dashboard UX 优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Dashboard 页面 7 个 UX 问题，提升数据展示准确性、交互反馈和视觉表现力

**Architecture:** 纯前端修改（HTML/CSS/JS），不涉及后端 API 变更。后端已返回所有需要的字段（`sample_count`, `window`, `start_date`, `end_date`, `window_return`），前端只需正确使用。

**Tech Stack:** Vanilla JS + CSS (no framework), FastAPI backend, SQLite/PostgreSQL

---

## 文件清单

| 文件路径 | 职责 | 修改类型 |
|---------|------|---------|
| `src/api/dashboard_page/scripts/dashboard.js` | 前端交互逻辑 | Modify |
| `src/api/dashboard_page/styles/dashboard.css` | 面板样式 | Modify |
| `src/api/dashboard_page/partials/view_dashboard.html` | 页面结构 | Modify |
| `tests/test_dashboard_page_contract.py` | HTML 契约测试 | Modify |

---

## Phase 1: 高优先级 — 数据展示与信息传达（预估 60 min）

### Task 1: 90天/YTD 数据不足时显示警告

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (renderPerformance function, around line 343)
- Modify: `tests/test_dashboard_page_contract.py`

**验收标准:**
1. 当 `sample_count < windowDays * 0.8` 时，range-data 显示黄色警告文字 "⚠️ 数据不足 X 天，仅显示最近 Y 天"
2. 7天/30天数据充足时，不显示警告
3. 警告不影响收益数值和日期范围的正常展示

- [ ] **Step 1: 写失败的契约测试**

```python
# tests/test_dashboard_page_contract.py (追加)
def test_render_dashboard_html_contains_insufficient_data_warning_helper():
    html = render_dashboard_html()
    assert "insufficientDataWarningHtml" in html
    assert "数据不足" in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_insufficient_data_warning_helper -v`
Expected: FAIL

- [ ] **Step 3: 实现 insufficientDataWarningHtml 函数**

在 `dashboard.js` 中 `formatSignedRateValue` 函数之后添加：

```javascript
function insufficientDataWarningHtml(sampleCount, window) {
  var expectedDays = { '7d': 7, '30d': 30, '90d': 90, 'ytd': 365 };
  var threshold = (expectedDays[window] || 30) * 0.8;
  if (!sampleCount || sampleCount >= threshold) return '';
  return '<div class="range-card-warning">⚠️ 数据不足 ' + (expectedDays[window] || 30) + ' 天，仅显示最近 ' + sampleCount + ' 天</div>';
}
```

- [ ] **Step 4: 修改 renderPerformance 中的 range-data 渲染**

在 `renderPerformance` 函数中，当 `windowReturn` 存在时的 HTML 模板中追加 warning：

```javascript
if (rangeDataEl) {
  var windowReturn = perf.window_return;
  var sampleCount = perf.sample_count;
  var startDate = perf.start_date;
  var endDate = perf.end_date;
  if (windowReturn !== undefined && windowReturn !== null && sampleCount) {
    var returnClass = windowReturn >= 0 ? 'green' : 'red';
    var returnText = formatSignedRateValue(windowReturn);
    var startText = startDate ? formatDate(startDate) : '--';
    var endText = endDate ? formatDate(endDate) : '--';
    rangeDataEl.innerHTML =
      '<div class="range-card">' +
        '<div class="range-card-head">' +
          '<span class="range-card-label">' + escapeHtml(normalizeWindowLabel(selectedPerformanceWindow)) + '收益</span>' +
          '<span class="range-card-window">' + escapeHtml(startText) + ' ~ ' + escapeHtml(endText) + '</span>' +
        '</div>' +
        '<div class="range-card-value ' + returnClass + '">' + escapeHtml(returnText) + '</div>' +
        '<div class="range-card-sub">' + escapeHtml(String(sampleCount)) + ' 个交易日样本</div>' +
        insufficientDataWarningHtml(sampleCount, selectedPerformanceWindow) +
      '</div>';
  } else {
    var cards = toList(perf.comparison_cards);
    if (!cards.length) {
      rangeDataEl.innerHTML = '<span class="range-placeholder">当前区间暂无表现对比数据</span>';
    } else {
      rangeDataEl.innerHTML = cards.map(renderPerformanceCard).join('');
    }
  }
}
```

- [ ] **Step 5: 添加 warning 样式**

在 `dashboard.css` 的 `.range-card-sub` 之后追加：

```css
.range-card-warning{font-size:11px;color:var(--yellow);margin-top:2px;padding:2px 6px;background:rgba(234,179,8,.08);border-radius:4px;border-left:2px solid var(--yellow)}
```

- [ ] **Step 6: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/styles/dashboard.css tests/test_dashboard_page_contract.py
git commit -m "feat: show insufficient data warning in range-data panel"
```

---

### Task 2: 运行卡片添加"点击查看案件"提示

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (renderRunCard function, around line 1413)
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `tests/test_dashboard_page_contract.py`

**验收标准:**
1. 标记为 "完整案件" 的卡片底部显示 "点击查看案件详情" 提示
2. 标记为 "概要" 的卡片不显示该提示
3. hover 时提示文字更加明显

- [ ] **Step 1: 写失败的契约测试**

```python
# tests/test_dashboard_page_contract.py (追加)
def test_render_dashboard_html_contains_run_card_hint():
    html = render_dashboard_html()
    assert "run-card-hint" in html
    assert "点击查看案件详情" in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_run_card_hint -v`
Expected: FAIL

- [ ] **Step 3: 修改 renderRunCard 函数**

在 `dashboard.js` 中的 `renderRunCard` 函数，在 `run-card-note` 之后、return string 的闭合标签之前，添加 hint：

```javascript
function renderRunCard(run) {
  var active = selectedHistoryRunMeta && normalizeText(selectedHistoryRunMeta.id, '') === normalizeText(run.id, '');
  var statusClass = runStatusClass(run.status);
  var netPnl = formatSignedCurrency(run.net_pnl);
  var details = [
    run.trade_date || '--',
    run.market || '--',
    run.supports_case_view ? '完整案件' : '概要',
  ];
  var counts = [
    '决策 ' + (run.decision_count ?? 0),
    '目标 ' + (run.target_count ?? 0),
    '订单 ' + (run.order_count ?? 0),
    '观察 ' + (run.watchlist_count ?? 0),
  ];
  var note = normalizeText(run.error_message, '');
  var hint = run.supports_case_view
    ? '<div class="run-card-hint"><span class="hint-icon">👁</span><span class="hint-text">点击查看案件详情</span></div>'
    : '';
  return '<button type="button" class="run-card ' + (active ? 'active' : '') + '" data-run-id="' + escapeHtml(run.id) + '" onclick="selectHistoryRun(\'' + escapeHtml(run.id) + '\')">' +
    '<div class="run-card-head">' +
      '<span class="run-card-source ' + run.source + '">' + escapeHtml(runSourceLabel(run.source)) + '</span>' +
      '<span class="run-card-status ' + statusClass + '">' + escapeHtml(runStatusLabel(run.status)) + '</span>' +
    '</div>' +
    '<div class="run-card-title">' + escapeHtml(run.id) + '</div>' +
    '<div class="run-card-meta">' +
      details.map(function(item) { return '<span>' + escapeHtml(item) + '</span>'; }).join('') +
    '</div>' +
    '<div class="run-card-badges">' +
      counts.map(function(item) { return '<span class="run-mini-chip">' + escapeHtml(item) + '</span>'; }).join('') +
      '<span class="run-mini-chip pnl">' + escapeHtml(netPnl) + '</span>' +
    '</div>' +
    '<div class="run-card-note ' + (note ? 'show' : '') + '">' + escapeHtml(note || (run.decision_mode ? (run.decision_mode + ' · ' + (run.execution_mode || '--')) : '')) + '</div>' +
    hint +
  '</button>';
}
```

- [ ] **Step 4: 添加 hint 样式**

在 `dashboard.css` 中 `.run-card-note.show` 之后追加：

```css
.run-card-hint{display:flex;align-items:center;gap:4px;margin-top:8px;padding-top:6px;border-top:1px dashed var(--stroke);font-size:11px;color:var(--dim);opacity:.5;transition:opacity .2s,color .2s}
.run-card:hover .run-card-hint{opacity:1;color:var(--accent)}
.hint-icon{font-size:10px}
.hint-text{letter-spacing:.3px}
```

- [ ] **Step 5: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/styles/dashboard.css tests/test_dashboard_page_contract.py
git commit -m "feat: add click hint for case-view run cards"
```

---

### Task 3: Footer 文案优化

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (renderRunCenter function, around line 1485)

**验收标准:**
1. 无更多数据时显示 "已显示全部 X 条记录"
2. 有更多数据时，加载更多按钮显示 "加载更多 (已显示 X 条)"

- [ ] **Step 1: 修改 renderRunCenter 中的 footer 渲染**

将 `dashboard.js` 中 `renderRunCenter` 函数的 footer 部分改为：

```javascript
if (footer) {
  footer.innerHTML = historyPanelHasMore
    ? '<button type="button" class="run-load-more" id="run-history-load-more" onclick="loadMoreHistoryRuns()" ' + (historyPanelLoading ? 'disabled' : '') + '>' +
      (historyPanelLoading ? '加载中...' : '加载更多 (已显示 ' + historyRuns.length + ' 条)') +
      '</button>'
    : '<div class="run-center-status">已显示全部 ' + historyRuns.length + ' 条记录</div>';
  setupHistoryScrollObserver(footer);
}
```

- [ ] **Step 2: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js
git commit -m "feat: improve footer text to show total count"
```

---

## Phase 2: 中优先级 — 交互反馈与状态优化（预估 45 min）

### Task 4: 案件阶段按钮激活状态增强

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css` (case-stage-rail button styles, around line 362)

**验收标准:**
1. 激活按钮有明显的背景提升效果（translateY + box-shadow）
2. 激活按钮的数字计数更加醒目（加粗 + 放大）
3. hover 非激活按钮时有微妙的过渡效果

- [ ] **Step 1: 更新 case-stage-rail 按钮样式**

在 `dashboard.css` 中将以下样式替换：

```css
/* 替换前 */
.case-stage-rail button.active{border-color:var(--accent);color:var(--bg);background:var(--accent)}
.case-stage-rail button:hover:not(.active){border-color:rgba(77,212,198,.35);color:var(--fg)}

/* 替换后 */
.case-stage-rail button.active{border-color:var(--accent);color:var(--bg);background:var(--accent);box-shadow:0 4px 12px rgba(77,212,198,.3);transform:translateY(-2px)}
.case-stage-rail button.active strong{color:var(--bg);font-weight:800;font-size:13px}
.case-stage-rail button:hover:not(.active){border-color:rgba(77,212,198,.35);color:var(--fg);transform:translateY(-1px);background:rgba(77,212,198,.06)}
```

- [ ] **Step 2: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard_page/styles/dashboard.css
git commit -m "feat: enhance case-stage-rail active button visual feedback"
```

---

### Task 5: 时间显示优化

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (formatTime function, around line 112 in utils.js, and renderDecisions/renderOrders functions)

**验收标准:**
1. 时间字段在没有数据时显示 "未记录" 而非 "--"
2. 有数据时显示格式化的时间
3. 不影响 formatDate 等其他函数的行为

- [ ] **Step 1: 创建 displayTimeValue 辅助函数**

在 `dashboard.js` 顶部（switchTab 函数之前）添加：

```javascript
function displayTimeValue(raw) {
  var formatted = formatTime(raw);
  return formatted === '--' ? '未记录' : formatted;
}
```

- [ ] **Step 2: 更新 renderDecisions 中的时间渲染**

在 `renderDecisions` 函数中，将：

```javascript
// 替换前
var time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
return '<tr><td>' + escapeHtml(time) + '</td>' +

// 替换后
var time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp']));
return '<tr><td>' + escapeHtml(time) + '</td>' +
```

- [ ] **Step 3: 更新 renderOrders 中的时间渲染**

在 `renderOrders` 函数中，将：

```javascript
// 替换前
var time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
return '<tr><td>' + escapeHtml(time) + '</td>' +

// 替换后
var time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp']));
return '<tr><td>' + escapeHtml(time) + '</td>' +
```

- [ ] **Step 4: 更新 renderErrorEvents 中的时间渲染**

在 `renderErrorEvents` 函数中，将：

```javascript
// 替换前
var time = formatTime(pickFirst(item, ['created_at', 'timestamp', 'time']));
return '<tr><td>' + escapeHtml(time) + '</td>' +

// 替换后
var time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp', 'time']));
return '<tr><td>' + escapeHtml(time) + '</td>' +
```

- [ ] **Step 5: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js
git commit -m "feat: replace -- with 未记录 for missing time fields"
```

---

### Task 6: 区间切换时显示加载状态

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (loadPerformancePanel function, around line 1362)

**验收标准:**
1. 切换 7天/30天/90天/YTD 时，canvas 区域显示 "加载中..."
2. range-data 区域显示骨架屏（placeholder 条）
3. 加载完成后正常更新数据

- [ ] **Step 1: 添加 showPerformanceLoading 函数**

在 `loadPerformancePanel` 函数之前添加：

```javascript
function showPerformanceLoading() {
  var canvas = document.getElementById('perf-nav-canvas');
  var rangeData = document.getElementById('range-data');
  var titleEl = document.getElementById('nav-curve-title');
  if (canvas) {
    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    ctx.fillStyle = 'rgba(120, 120, 120, 0.5)';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('加载中...', canvas.clientWidth / 2, canvas.clientHeight / 2);
  }
  if (rangeData) {
    rangeData.innerHTML = '<span class="range-placeholder">加载中...</span>';
  }
}
```

- [ ] **Step 2: 在 loadPerformancePanel 中调用 showPerformanceLoading**

在 `loadPerformancePanel` 函数的 try 块之前添加：

```javascript
async function loadPerformancePanel(market, window) {
  var win = window || selectedPerformanceWindow || '7d';
  selectedPerformanceWindow = win;
  showPerformanceLoading();
  try {
    var res = await fetch(PERFORMANCE_API + '?market=' + market + '&account_kind=auto&window=' + win);
    if (!res.ok) return;
    var data = await parseResponseBody(res);
    renderPerformance(data);
  } catch (_) {}
}
```

- [ ] **Step 3: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js
git commit -m "feat: add loading state during performance window switch"
```

---

## Phase 3: 低优先级 — 视觉细节优化（预估 20 min）

### Task 7: 盈亏视觉增强

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js` (renderRunCard function, around line 1440)
- Modify: `src/api/dashboard_page/styles/dashboard.css`

**验收标准:**
1. 盈利金额使用绿色背景 + 绿色文字 + 加粗
2. 亏损金额使用红色背景 + 红色文字 + 加粗
3. 不影响其他 badge 样式

- [ ] **Step 1: 更新 run-card 的 PnL badge class**

在 `renderRunCard` 函数中，将 PnL chip 部分改为：

```javascript
var pnlClass = run.net_pnl > 0 ? 'green' : (run.net_pnl < 0 ? 'red' : '');
var counts = [
  '决策 ' + (run.decision_count ?? 0),
  '目标 ' + (run.target_count ?? 0),
  '订单 ' + (run.order_count ?? 0),
  '观察 ' + (run.watchlist_count ?? 0),
];
```

并更新 badges 渲染：

```javascript
'<div class="run-card-badges">' +
  counts.map(function(item) { return '<span class="run-mini-chip">' + escapeHtml(item) + '</span>'; }).join('') +
  '<span class="run-mini-chip pnl ' + pnlClass + '">' + escapeHtml(netPnl) + '</span>' +
'</div>' +
```

- [ ] **Step 2: 添加 PnL 增强样式**

在 `dashboard.css` 中 `.run-mini-chip.pnl` 之后追加：

```css
.run-mini-chip.pnl.green{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.25)}
.run-mini-chip.pnl.red{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.25)}
```

- [ ] **Step 3: 运行全部测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_api.py -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/styles/dashboard.css
git commit -m "feat: enhance P&L visual in run cards with colored badges"
```

---

## 总体验标准

| 维度 | 验收要求 |
|------|---------|
| 测试 | 所有测试通过：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q` |
| 代码质量 | 无冗余代码、无魔法数字、函数职责单一 |
| 浏览器验证 | `http://13.214.201.113:8000/dashboard` 上 7个问题全部解决 |
| 具体场景 | 切换90天→显示黄色警告卡片 / 完整案件卡片底部有点击提示 / 无更多记录时显示"已显示全部" / 阶段按钮激活态提升 / 时间不再显示-- / 切换区间有加载反馈 / PnL红绿对比醒目 |
