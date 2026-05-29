# 实时行情搜索功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在实时行情页面添加股票搜索功能，支持临时查看行情并提供添加到观察列表的按钮

**Architecture:** 前端在 `dashboard.html` 的实时行情视图中添加搜索栏，调用已有的后端 API `/api/v1/market/stocks` 搜索股票，使用 `/api/v1/market/bulk` 获取行情数据

**Tech Stack:** HTML/CSS/JavaScript 单文件应用，FastAPI 后端（已有 API）

---

## 文件结构

| 文件 | 修改类型 | 职责 |
|------|----------|------|
| `src/api/dashboard.html:433-448` | 修改 | 添加搜索栏 HTML |
| `src/api/dashboard.html` `<style>` | 修改 | 添加搜索栏样式 |
| `src/api/dashboard.html` `<script>` | 修改 | 添加搜索函数 |

---

## Task 1: 添加搜索栏样式

**Files:**
- Modify: `src/api/dashboard.html` - 在 `/* ── BADGES ── */` 注释之前添加样式

- [ ] **Step 1: 添加搜索栏 CSS 样式**

在 `src/api/dashboard.html` 的 `<style>` 标签内，找到 `/* ── BADGES ── */` 注释，在其之前添加：

```css
/* ── SEARCH BAR ── */
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.search-bar input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--fg);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  width: 320px;
  font-family: inherit;
}
.search-bar input:focus {
  outline: none;
  border-color: var(--accent);
}
.search-bar input::placeholder {
  color: var(--dim);
}
```

- [ ] **Step 2: 验证样式添加成功**

打开 `src/api/dashboard.html`，搜索 `/* ── SEARCH BAR ── */`，确认样式已添加。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "style: add market search bar CSS styles"
```

---

## Task 2: 添加搜索栏 HTML

**Files:**
- Modify: `src/api/dashboard.html:433-448` - 在实时行情视图中添加搜索栏

- [ ] **Step 1: 添加搜索栏 HTML 结构**

在 `src/api/dashboard.html` 中找到以下代码：

```html
<div class="view" id="view-market">
  <h2>实时行情</h2>
  <table class="market-table">
```

将其替换为：

```html
<div class="view" id="view-market">
  <h2>实时行情</h2>
  <div class="search-bar">
    <input type="text" id="stock-search-input" placeholder="输入股票代码或名称（如：600519 或 贵州茅台）">
    <button class="run-btn" onclick="searchStock()" style="padding:8px 16px;font-size:12px">搜索</button>
    <button class="save-btn" onclick="addSearchToWatchlist()" style="width:auto;padding:8px 16px;font-size:12px">+ 添加到观察列表</button>
    <button class="run-btn" onclick="exitSearchMode()" style="padding:8px 16px;font-size:12px;background:var(--surface2)">返回观察列表</button>
    <span id="search-status" style="font-size:11px;color:var(--dim)"></span>
  </div>
  <table class="market-table">
```

- [ ] **Step 2: 验证 HTML 添加成功**

打开 `src/api/dashboard.html`，搜索 `id="stock-search-input"`，确认搜索栏已添加。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add market search bar HTML structure"
```

---

## Task 3: 添加搜索 JavaScript 函数

**Files:**
- Modify: `src/api/dashboard.html` `<script>` - 在 `refreshMarketQuotes()` 函数之后添加搜索逻辑

- [ ] **Step 1: 添加搜索相关变量和函数**

在 `src/api/dashboard.html` 的 `<script>` 标签内，找到 `refreshMarketQuotes()` 函数的结束花括号 `}`，在其之后添加：

```javascript
// ── 搜索相关变量 ──
let searchResults = [];
let selectedSearchIndex = -1;
let isSearchMode = false;

async function searchStock() {
  const input = document.getElementById('stock-search-input');
  const statusEl = document.getElementById('search-status');
  const query = input.value.trim();
  
  if (!query) {
    statusEl.textContent = '请输入股票代码或名称';
    statusEl.style.color = 'var(--yellow)';
    return;
  }
  
  statusEl.textContent = '搜索中...';
  statusEl.style.color = 'var(--yellow)';
  
  try {
    const res = await fetch(`/api/v1/market/stocks?query=${encodeURIComponent(query)}&limit=20`);
    if (!res.ok) {
      throw new Error(`搜索失败 (${res.status})`);
    }
    
    searchResults = await res.json();
    selectedSearchIndex = -1;
    
    if (searchResults.length === 0) {
      statusEl.textContent = '未找到匹配的股票';
      statusEl.style.color = 'var(--yellow)';
      return;
    }
    
    statusEl.textContent = `找到 ${searchResults.length} 个结果`;
    statusEl.style.color = 'var(--green)';
    isSearchMode = true;
    
    await loadSearchQuotes();
    
  } catch (error) {
    statusEl.textContent = `搜索失败: ${error.message}`;
    statusEl.style.color = 'var(--red)';
  }
}

async function loadSearchQuotes() {
  if (searchResults.length === 0) return;
  
  const symbols = searchResults.map(s => s.symbol);
  const tb = document.getElementById('tb-market-full');
  
  try {
    const res = await fetch('/api/v1/market/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(symbols),
    });
    
    if (!res.ok) {
      throw new Error('获取行情失败');
    }
    
    const quotes = await res.json();
    renderSearchQuotes(quotes);
    
  } catch (error) {
    tb.innerHTML = `<tr><td colspan="12" class="market-empty" style="color:var(--red)">获取行情失败: ${error.message}</td></tr>`;
  }
}

function renderSearchQuotes(quotes) {
  const tb = document.getElementById('tb-market-full');
  if (!quotes || quotes.length === 0) {
    tb.innerHTML = '<tr><td colspan="12" class="market-empty">暂无行情数据</td></tr>';
    return;
  }
  
  const now = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  tb.innerHTML = quotes.map((item, index) => {
    const symbol = normalizeText(item.symbol, '--');
    const name = normalizeText(item.name, '');
    const close = Number(item.close);
    const changePct = Number(item.change_pct);
    const cls = (changePct ?? 0) > 0 ? 'quote-up' : (changePct ?? 0) < 0 ? 'quote-down' : '';
    const rowCls = (changePct ?? 0) > 0 ? 'row-up' : (changePct ?? 0) < 0 ? 'row-down' : '';
    const changeAmt = Number(item.prev_close) ? (close - Number(item.prev_close)).toFixed(2) : '--';
    const selectedStyle = index === selectedSearchIndex ? 'background:rgba(96,165,250,.15)' : '';
    
    return `<tr class="${rowCls}" onclick="selectSearchResult(${index})" style="cursor:pointer;${selectedStyle}">
      <td style="color:var(--dim);font-size:11px">${escapeHtml(now)}</td>
      <td>${escapeHtml(symbol)} ${escapeHtml(name)}</td>
      <td class="${cls}">${escapeHtml(formatNumber(close))}</td>
      <td class="${cls}">${escapeHtml(String(changeAmt))}</td>
      <td class="${cls}">${escapeHtml(formatSignedPercent(changePct))}</td>
      <td>${escapeHtml(formatNumber(item.open))}</td>
      <td>${escapeHtml(formatNumber(item.high))}</td>
      <td>${escapeHtml(formatNumber(item.low))}</td>
      <td>${escapeHtml(formatVolume(item.volume))}</td>
      <td>${escapeHtml(formatNumber(item.turnover))}%</td>
      <td>${escapeHtml(formatNumber(item.amplitude))}%</td>
      <td>${escapeHtml(formatNumber(item.volume_ratio))}</td>
    </tr>`;
  }).join('');
}

function selectSearchResult(index) {
  selectedSearchIndex = index;
  loadSearchQuotes();
}

function addSearchToWatchlist() {
  if (selectedSearchIndex < 0 || selectedSearchIndex >= searchResults.length) {
    document.getElementById('search-status').textContent = '请先点击选择一只股票';
    document.getElementById('search-status').style.color = 'var(--yellow)';
    return;
  }
  
  const stock = searchResults[selectedSearchIndex];
  const watchlistInput = document.getElementById('cfg-watchlist');
  const symbols = watchlistInput.value.split(',').map(s => s.trim()).filter(Boolean);
  
  if (symbols.includes(stock.symbol)) {
    document.getElementById('search-status').textContent = `${stock.symbol} 已在观察列表中`;
    document.getElementById('search-status').style.color = 'var(--yellow)';
    return;
  }
  
  symbols.push(stock.symbol);
  watchlistInput.value = symbols.join(',');
  
  document.getElementById('search-status').textContent = `已添加 ${stock.symbol} 到观察列表`;
  document.getElementById('search-status').style.color = 'var(--green)';
}

function exitSearchMode() {
  isSearchMode = false;
  searchResults = [];
  selectedSearchIndex = -1;
  document.getElementById('stock-search-input').value = '';
  document.getElementById('search-status').textContent = '';
  refreshMarketQuotes();
}

document.getElementById('stock-search-input').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    searchStock();
  }
});
```

- [ ] **Step 2: 验证函数添加成功**

打开 `src/api/dashboard.html`，搜索 `async function searchStock()`，确认函数已添加。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add market search JavaScript functions"
```

---

## Task 4: 修改自动刷新逻辑

**Files:**
- Modify: `src/api/dashboard.html` `<script>` - 修改 `setInterval` 逻辑，搜索模式下不自动刷新

- [ ] **Step 1: 修改行情自动刷新逻辑**

在 `src/api/dashboard.html` 的 `<script>` 标签内，找到文件末尾的 `setInterval` 调用：

```javascript
setInterval(() => {
  if (!simRunning) {
    refreshMarketQuotes();
  }
}, 30000);  // 行情：30秒
```

将其替换为：

```javascript
setInterval(() => {
  if (!simRunning && !isSearchMode) {
    refreshMarketQuotes();
  }
}, 30000);  // 行情：30秒（搜索模式下不自动刷新）
```

- [ ] **Step 2: 验证修改成功**

打开 `src/api/dashboard.html`，搜索 `!isSearchMode`，确认逻辑已修改。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "fix: disable auto-refresh in search mode"
```

---

## 验收标准

### 功能验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 输入股票代码（如 600519）点击搜索 | 显示贵州茅台的实时行情 | 在搜索框输入 600519，点击搜索按钮 |
| 输入股票名称（如 贵州）点击搜索 | 显示匹配的股票列表 | 在搜索框输入 贵州，点击搜索按钮 |
| 搜索结果中点击某行 | 该行高亮显示 | 点击搜索结果中的某一行 |
| 点击"+ 添加到观察列表" | 观察列表 textarea 中添加该股票代码 | 选中一行后点击添加按钮 |
| 点击"返回观察列表" | 恢复显示原观察列表的行情 | 点击返回按钮 |
| 搜索框按回车 | 触发搜索 | 在搜索框中输入后按回车 |
| 输入不存在的代码 | 显示"未找到匹配的股票" | 输入不存在的代码如 999999 |
| 观察列表中已存在的股票点击添加 | 提示"已在观察列表中" | 尝试添加已存在的股票 |

### UI 验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 搜索栏布局 | 输入框、按钮水平排列，间距适当 | 查看实时行情页面 |
| 搜索框 placeholder | 显示"输入股票代码或名称（如：600519 或 贵州茅台）" | 查看搜索框 |
| 搜索状态提示 | 成功显示绿色，失败显示红色，加载显示黄色 | 执行搜索操作 |
| 选中行高亮 | 蓝色半透明背景 | 点击搜索结果行 |
| 按钮样式 | 搜索按钮蓝色，添加按钮绿色，返回按钮灰色 | 查看按钮颜色 |

### 集成验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 添加股票后点击"保存配置" | 配置保存成功，刷新后观察列表包含新添加的股票 | 添加股票后保存配置并刷新页面 |
| 30秒自动刷新 | 搜索模式下不会自动刷新 | 搜索后等待30秒观察 |
| 切换到工作台再切回 | 保持搜索状态 | 切换视图后返回 |

---

**计划完成。两种执行方式：**

**1. Subagent-Driven（推荐）** - 每个 Task 派发一个子代理，任务间审查

**2. Inline Execution** - 在当前会话中执行，批量执行带检查点

**选择哪种方式？**
