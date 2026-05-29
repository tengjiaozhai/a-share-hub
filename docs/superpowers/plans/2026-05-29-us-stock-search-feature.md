# 美股搜索功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在实时行情搜索功能中添加美股搜索支持，使用 akshare 的 `stock_us_famous_spot_em` API 获取知名美股列表

**Architecture:** 后端添加美股搜索 API，前端添加市场选择下拉框，支持 A 股和美股切换搜索

**Tech Stack:** FastAPI, akshare, HTML/CSS/JavaScript

---

## 文件结构

| 文件 | 修改类型 | 职责 |
|------|----------|------|
| `src/api/routes_market.py` | 修改 | 添加美股搜索 API |
| `src/api/dashboard.html` | 修改 | 添加市场选择下拉框和美股搜索逻辑 |

---

## Task 1: 添加美股搜索 API

**Files:**
- Modify: `src/api/routes_market.py:18-39` - 添加美股搜索 endpoint

- [ ] **Step 1: 添加美股搜索 API endpoint**

在 `src/api/routes_market.py` 中找到 `list_market_stocks` 函数，在其之后添加：

```python
@router.get("/stocks/us")
def list_us_stocks(
    query: str = Query("", max_length=50),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    """获取美股知名股票列表，支持搜索过滤。"""
    try:
        import akshare as ak
        df = ak.stock_us_famous_spot_em()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取美股列表失败: {e}")
    
    # 标准化列名
    df = df.rename(columns={
        "名称": "name",
        "代码": "symbol",
        "最新价": "close",
        "涨跌额": "change",
        "涨跌幅": "change_pct",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "昨收价": "prev_close",
        "总市值": "market_cap",
        "市盈率": "pe_ratio",
    })
    
    # 搜索过滤
    q = query.strip()
    if q:
        df = df[
            df["symbol"].str.contains(q, case=False, na=False)
            | df["name"].str.contains(q, case=False, na=False)
        ]
    
    return df.head(limit).to_dict("records")
```

- [ ] **Step 2: 验证 API 添加成功**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && python3 -c "from src.api.routes_market import list_us_stocks; print('函数定义成功')"`

Expected: 输出 "函数定义成功"

- [ ] **Step 3: Commit**

```bash
git add src/api/routes_market.py
git commit -m "feat: add US stock search API endpoint"
```

---

## Task 2: 添加市场选择下拉框

**Files:**
- Modify: `src/api/dashboard.html` - 在搜索栏添加市场选择

- [ ] **Step 1: 添加市场选择下拉框 HTML**

在 `src/api/dashboard.html` 中找到搜索栏的 `<input>` 元素，在其之前添加：

```html
<div class="search-bar">
  <select id="market-select" style="background:var(--bg);border:1px solid var(--border);color:var(--fg);padding:8px 12px;border-radius:6px;font-size:13px;font-family:inherit;">
    <option value="a">A 股</option>
    <option value="us">美股</option>
  </select>
  <input type="text" id="stock-search-input" placeholder="输入股票代码或名称（如：600519 或 贵州茅台）">
  <button class="run-btn" onclick="searchStock()" style="padding:8px 16px;font-size:12px">搜索</button>
  <button class="save-btn" onclick="addSearchToWatchlist()" style="width:auto;padding:8px 16px;font-size:12px">+ 添加到观察列表</button>
  <button class="run-btn" onclick="exitSearchMode()" style="padding:8px 16px;font-size:12px;background:var(--surface2)">返回观察列表</button>
  <span id="search-status" style="font-size:11px;color:var(--dim)"></span>
</div>
```

- [ ] **Step 2: 验证 HTML 添加成功**

打开 `src/api/dashboard.html`，搜索 `id="market-select"`，确认下拉框已添加。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add market selector dropdown in search bar"
```

---

## Task 3: 修改搜索函数支持美股

**Files:**
- Modify: `src/api/dashboard.html` - 修改 `searchStock()` 函数

- [ ] **Step 1: 修改 searchStock 函数支持市场选择**

在 `src/api/dashboard.html` 中找到 `async function searchStock()` 函数，将其替换为：

```javascript
async function searchStock() {
  const input = document.getElementById('stock-search-input');
  const statusEl = document.getElementById('search-status');
  const marketSelect = document.getElementById('market-select');
  const query = input.value.trim();
  const market = marketSelect.value;
  
  if (!query) {
    statusEl.textContent = '请输入股票代码或名称';
    statusEl.style.color = 'var(--yellow)';
    return;
  }
  
  statusEl.textContent = '搜索中...';
  statusEl.style.color = 'var(--yellow)';
  
  try {
    let url;
    if (market === 'us') {
      url = `/api/v1/market/stocks/us?query=${encodeURIComponent(query)}&limit=20`;
    } else {
      url = `/api/v1/market/stocks?query=${encodeURIComponent(query)}&limit=20`;
    }
    
    const res = await fetch(url);
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
    
    if (market === 'us') {
      renderUsSearchQuotes(searchResults);
    } else {
      await loadSearchQuotes();
    }
    
  } catch (error) {
    statusEl.textContent = `搜索失败: ${error.message}`;
    statusEl.style.color = 'var(--red)';
  }
}
```

- [ ] **Step 2: 添加美股行情渲染函数**

在 `searchStock()` 函数之后添加：

```javascript
function renderUsSearchQuotes(quotes) {
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
    const changeAmt = normalizeText(item.change, '--');
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
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>`;
  }).join('');
}
```

- [ ] **Step 3: 验证函数添加成功**

打开 `src/api/dashboard.html`，搜索 `function renderUsSearchQuotes`，确认函数已添加。

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add US stock search and render functions"
```

---

## Task 4: 更新搜索框 placeholder

**Files:**
- Modify: `src/api/dashboard.html` - 添加市场切换时更新 placeholder

- [ ] **Step 1: 添加市场切换事件处理**

在 `src/api/dashboard.html` 的 `<script>` 标签内，找到搜索框回车事件的代码，在其之后添加：

```javascript
// 市场切换时更新 placeholder
document.getElementById('market-select').addEventListener('change', event => {
  const input = document.getElementById('stock-search-input');
  if (event.target.value === 'us') {
    input.placeholder = '输入美股代码或名称（如：AAPL 或 苹果）';
  } else {
    input.placeholder = '输入股票代码或名称（如：600519 或 贵州茅台）';
  }
});
```

- [ ] **Step 2: 验证事件处理添加成功**

打开 `src/api/dashboard.html`，搜索 `market-select.*addEventListener`，确认事件处理已添加。

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: update placeholder on market switch"
```

---

## 验收标准

### 功能验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 选择"A 股"市场搜索 | 显示 A 股搜索结果 | 选择 A 股，输入 600519，点击搜索 |
| 选择"美股"市场搜索 | 显示美股搜索结果 | 选择美股，输入 AAPL，点击搜索 |
| 搜索美股名称 | 显示匹配的美股列表 | 选择美股，输入 苹果，点击搜索 |
| 搜索框 placeholder 更新 | 切换市场时 placeholder 变化 | 切换市场选择下拉框 |
| 美股行情显示 | 显示美股实时行情数据 | 搜索美股后查看表格数据 |
| 添加美股到观察列表 | 成功添加美股代码 | 选中美股后点击添加按钮 |

### UI 验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 市场选择下拉框 | 显示在搜索框左侧 | 查看实时行情页面 |
| 下拉框选项 | 包含"A 股"和"美股" | 点击下拉框 |
| placeholder 更新 | 切换市场后 placeholder 变化 | 切换市场选择 |
| 美股行情表格 | 显示正确的列数据 | 搜索美股后查看表格 |

### API 验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| GET /api/v1/market/stocks/us | 返回美股列表 | 调用 API 验证返回数据 |
| 搜索过滤 | 返回匹配的结果 | 传入 query 参数测试 |
| limit 参数 | 限制返回数量 | 传入 limit 参数测试 |

---

**计划完成。两种执行方式：**

**1. Subagent-Driven（推荐）** - 每个 Task 派发一个子代理，任务间审查

**2. Inline Execution** - 在当前会话中执行，批量执行带检查点

**选择哪种方式？**
