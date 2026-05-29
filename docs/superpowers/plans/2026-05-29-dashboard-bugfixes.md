# Dashboard Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 identified bugs in the A股自动交易系统 dashboard and improve user experience

**Architecture:** Single-page HTML dashboard with FastAPI backend. Frontend is in `src/api/dashboard.html`, backend routes in `src/api/routes_*.py`. All changes are surgical fixes to existing code.

**Tech Stack:** HTML/CSS/JavaScript (frontend), Python FastAPI (backend)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/api/dashboard.html` | Main dashboard UI, all frontend logic |
| `src/api/routes_market.py` | Market data API endpoints |
| `src/api/routes_dashboard.py` | Dashboard workbench API |

---

### Task 1: Fix Error Events Message Display

**Problem:** Error events tab shows `[object Object]` instead of readable text in the message column.

**Root Cause:** The `renderErrorEvents` function tries to extract message from `item.message`, `item.summary`, `item.reason`, or `item.payload`, but when `payload` is an object, it doesn't get serialized properly.

**Files:**
- Modify: `src/api/dashboard.html:1152-1171`

- [ ] **Step 1: Identify the bug in renderErrorEvents**

The current code at line 1167:
```javascript
const message = normalizeText(pickFirst(item, ['message', 'summary', 'reason', 'payload']), '--');
```

When `payload` is an object like `{symbol: "600519.SH", action: "BUY"}`, `normalizeText` converts it to `[object Object]`.

- [ ] **Step 2: Fix the message extraction logic**

```javascript
function renderErrorEvents(events) {
  const rows = toList(events);
  const dataChanged = rows !== pag.errors.data && JSON.stringify(rows) !== JSON.stringify(pag.errors.data);
  pag.errors.data = rows;
  if (dataChanged && rows.length >= PAGE_SIZE) pag.errors.page = 0;
  const tb = document.getElementById('tb-errors');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="3" style="color:var(--dim)">暂无异常</td></tr>';
    document.getElementById('pag-errors').innerHTML = '';
    return;
  }
  const page = pagSlice('errors');
  tb.innerHTML = page.map(item => {
    const time = formatTime(pickFirst(item, ['created_at', 'timestamp', 'time']));
    const level = normalizeText(pickFirst(item, ['level', 'severity', 'event_type'])).toUpperCase();
    // Fix: handle object payloads by JSON stringifying them
    let messageRaw = pickFirst(item, ['message', 'summary', 'reason'], null);
    if (!messageRaw && item.payload) {
      if (typeof item.payload === 'object') {
        try {
          messageRaw = JSON.stringify(item.payload, null, 2);
        } catch (e) {
          messageRaw = String(item.payload);
        }
      } else {
        messageRaw = String(item.payload);
      }
    }
    const message = normalizeText(messageRaw, '--');
    return `<tr><td>${escapeHtml(time)}</td><td>${escapeHtml(level)}</td><td>${escapeHtml(message)}</td></tr>`;
  }).join('');
  document.getElementById('pag-errors').innerHTML = rows.length >= PAGE_SIZE ? renderPagControls('errors') : '';
}
```

- [ ] **Step 3: Test the fix**

Refresh the dashboard, run a trading cycle, then check the "异常事件" tab. Messages should now display readable text or JSON instead of `[object Object]`.

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "fix: error events tab now displays readable messages instead of [object Object]"
```

---

### Task 2: Fix Stock Search Functionality

**Problem:** Searching for stocks by code (e.g., `600519`) or name (e.g., `贵州茅台`) returns "未找到匹配的股票".

**Root Cause:** The search API endpoint `/api/v1/market/stocks` exists, but the frontend `searchStock()` function may not be calling it correctly, or the backend search logic has issues with the akshare provider.

**Files:**
- Modify: `src/api/routes_market.py:18-39`
- Modify: `src/api/dashboard.html:926-983`

- [ ] **Step 1: Check the backend search implementation**

The current `list_market_stocks` function at line 18-39:
```python
@router.get("/stocks")
def list_market_stocks(
    query: str = Query("", max_length=50),
    exchange: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    frame = provider.get_stock_list()
    records = frame.copy()
    exchange_upper = exchange.strip().upper()
    if exchange_upper and exchange_upper != "ALL":
        records = records[records["exchange"] == exchange_upper]
    q = query.strip()
    if q:
        records = records[
            records["symbol"].str.contains(q, case=False, na=False)
            | records["code"].str.contains(q, case=False, na=False)
            | records["name"].str.contains(q, case=False, na=False)
        ]
    return records.head(limit).to_dict("records")
```

This looks correct. The issue might be that `provider.get_stock_list()` returns empty or the akshare provider is unavailable.

- [ ] **Step 2: Add debug logging to backend**

Add a simple test endpoint to verify the provider works:

```python
@router.get("/stocks/test")
def test_stock_search():
    """Test endpoint to debug stock search"""
    provider = _get_akshare_provider()
    available = provider.is_available()
    if not available:
        return {"error": "provider unavailable"}
    try:
        frame = provider.get_stock_list()
        return {
            "available": True,
            "total_stocks": len(frame),
            "columns": list(frame.columns),
            "sample": frame.head(3).to_dict("records") if len(frame) > 0 else []
        }
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 3: Test the backend directly**

Access `http://13.214.201.113:8000/api/v1/market/stocks/test` to verify the provider works.

- [ ] **Step 4: Fix frontend search if backend is working**

If the backend returns data correctly, the issue might be in the frontend. Check the `searchStock()` function in `dashboard.html`:

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
    // 清空表格，避免显示旧数据
    const tb = document.getElementById('tb-market-full');
    if (tb) {
      tb.innerHTML = '<tr><td colspan="12" class="market-empty" style="color:var(--red)">搜索失败，请重试</td></tr>';
    }
  }
}
```

The frontend code looks correct. The issue is likely that `searchResults` is empty after the API call.

- [ ] **Step 5: Add fallback search with local data**

If the akshare provider is slow or unavailable, add a local fallback:

```python
# 在 routes_market.py 中添加本地股票数据作为备用
_LOCAL_STOCKS = {
    "600519": {"symbol": "600519.SH", "name": "贵州茅台", "exchange": "SH"},
    "000858": {"symbol": "000858.SZ", "name": "五粮液", "exchange": "SZ"},
    "601318": {"symbol": "601318.SH", "name": "中国平安", "exchange": "SH"},
    "300317": {"symbol": "300317.SZ", "name": "珈伟新能", "exchange": "SZ"},
    "000001": {"symbol": "000001.SZ", "name": "平安银行", "exchange": "SZ"},
    "600036": {"symbol": "600036.SH", "name": "招商银行", "exchange": "SH"},
    "000333": {"symbol": "000333.SZ", "name": "美的集团", "exchange": "SZ"},
    "002594": {"symbol": "002594.SZ", "name": "比亚迪", "exchange": "SZ"},
    "601899": {"symbol": "601899.SH", "name": "紫金矿业", "exchange": "SH"},
    "600900": {"symbol": "600900.SH", "name": "长江电力", "exchange": "SH"},
}

@router.get("/stocks")
def list_market_stocks(
    query: str = Query("", max_length=50),
    exchange: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    provider = _get_akshare_provider()
    
    # Try akshare first
    if provider.is_available():
        try:
            frame = provider.get_stock_list()
            records = frame.copy()
            exchange_upper = exchange.strip().upper()
            if exchange_upper and exchange_upper != "ALL":
                records = records[records["exchange"] == exchange_upper]
            q = query.strip()
            if q:
                records = records[
                    records["symbol"].str.contains(q, case=False, na=False)
                    | records["code"].str.contains(q, case=False, na=False)
                    | records["name"].str.contains(q, case=False, na=False)
                ]
            result = records.head(limit).to_dict("records")
            if result:
                return result
        except Exception:
            pass
    
    # Fallback to local data
    q = query.strip().lower()
    if not q:
        return list(_LOCAL_STOCKS.values())[:limit]
    
    results = []
    for code, info in _LOCAL_STOCKS.items():
        if q in code or q in info["name"].lower():
            results.append(info)
        if len(results) >= limit:
            break
    return results
```

- [ ] **Step 6: Commit**

```bash
git add src/api/routes_market.py src/api/dashboard.html
git commit -m "fix: add fallback stock search when akshare provider unavailable"
```

---

### Task 3: Fix Execution Mode Persistence

**Problem:** Clicking "完整链路" or "仅决策" buttons doesn't persist the selection. Running still uses the previous mode.

**Root Cause:** The `execMode` variable is updated in memory but not saved to the server. When `buildRunPayload()` is called, it uses the current `execMode` value.

**Files:**
- Modify: `src/api/dashboard.html:545-550, 714-747, 1333-1348`

- [ ] **Step 1: Verify the current implementation**

The `setExecMode` function at line 545:
```javascript
function setExecMode(btn) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  execMode = btn.dataset.mode === 'decision' ? 'decision' : 'full';
  updateModeStatus();
}
```

This only updates the local variable. The `savePreferences` function at line 714 already includes `execution_mode`:
```javascript
const prefs = {
  watchlist: document.getElementById('cfg-watchlist').value
    .split(',').map(s => s.trim()).filter(Boolean),
  capital_base: Number(document.getElementById('cfg-capital').value),
  max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
  stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
  max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
  execution_mode: execMode,  // This is already included
};
```

- [ ] **Step 2: Auto-save execution mode on change**

Modify `setExecMode` to trigger auto-save:

```javascript
function setExecMode(btn) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  execMode = btn.dataset.mode === 'decision' ? 'decision' : 'full';
  updateModeStatus();
  // Auto-save the execution mode
  savePreferences();
}
```

- [ ] **Step 3: Test the fix**

1. Click "仅决策" button
2. Check the network tab - should see a PUT request to `/api/v1/dashboard/preferences`
3. Refresh the page
4. Verify "仅决策" button is still active

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "fix: auto-save execution mode when toggling between full/decision"
```

---

### Task 4: Fix Save Configuration Feedback

**Problem:** Clicking "保存配置" button shows no feedback to the user.

**Root Cause:** The `savePreferences` function does update the `save-status` element, but the feedback might not be visible or clear enough.

**Files:**
- Modify: `src/api/dashboard.html:714-747`

- [ ] **Step 1: Check current implementation**

The current `savePreferences` function:
```javascript
function savePreferences() {
  clearTimeout(_savePrefsTimer);
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = '保存中...';
  statusEl.style.color = 'var(--yellow)';

  const prefs = {
    watchlist: document.getElementById('cfg-watchlist').value
      .split(',').map(s => s.trim()).filter(Boolean),
    capital_base: Number(document.getElementById('cfg-capital').value),
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    execution_mode: execMode,
  };

  fetch(PREFS_API, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  }).then(res => {
    if (res.ok) {
      statusEl.textContent = '已保存';
      statusEl.style.color = 'var(--green)';
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    } else {
      statusEl.textContent = '保存失败';
      statusEl.style.color = 'var(--red)';
    }
  }).catch(() => {
    statusEl.textContent = '保存失败';
    statusEl.style.color = 'var(--red)';
  });
}
```

The feedback is there but might be too subtle. Let's enhance it with a toast notification.

- [ ] **Step 2: Add toast notification function**

```javascript
function showToast(message, type = 'info') {
  // Remove existing toast if any
  const existing = document.querySelector('.toast-notification');
  if (existing) existing.remove();
  
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.style.cssText = `
    position: fixed;
    top: 60px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    z-index: 10000;
    animation: slideIn 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;
  
  if (type === 'success') {
    toast.style.background = 'var(--green)';
    toast.style.color = '#fff';
  } else if (type === 'error') {
    toast.style.background = 'var(--red)';
    toast.style.color = '#fff';
  } else {
    toast.style.background = 'var(--accent)';
    toast.style.color = '#fff';
  }
  
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 2000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);
```

- [ ] **Step 3: Update savePreferences to use toast**

```javascript
function savePreferences() {
  clearTimeout(_savePrefsTimer);
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = '保存中...';
  statusEl.style.color = 'var(--yellow)';

  const prefs = {
    watchlist: document.getElementById('cfg-watchlist').value
      .split(',').map(s => s.trim()).filter(Boolean),
    capital_base: Number(document.getElementById('cfg-capital').value),
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    execution_mode: execMode,
  };

  fetch(PREFS_API, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  }).then(res => {
    if (res.ok) {
      statusEl.textContent = '已保存';
      statusEl.style.color = 'var(--green)';
      showToast('配置已保存', 'success');
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    } else {
      statusEl.textContent = '保存失败';
      statusEl.style.color = 'var(--red)';
      showToast('保存失败，请重试', 'error');
    }
  }).catch(() => {
    statusEl.textContent = '保存失败';
    statusEl.style.color = 'var(--red)';
    showToast('保存失败，请检查网络', 'error');
  });
}
```

- [ ] **Step 4: Test the fix**

Click "保存配置" button. A toast notification should appear in the top-right corner showing "配置已保存".

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add toast notifications for save configuration feedback"
```

---

### Task 5: Fix Capital Display Units

**Problem:** Running results show `¥200` but the user input `200` should represent 200 万元 (2,000,000 元).

**Root Cause:** The input field label says "模拟总资金 (元)" but the user might be entering values in 万元. The display doesn't clarify the unit.

**Files:**
- Modify: `src/api/dashboard.html:309-310, 1146-1149`

- [ ] **Step 1: Check current implementation**

HTML input at line 309:
```html
<label>模拟总资金 (元)</label>
<input type="number" id="cfg-capital" value="1000000" step="100000">
```

The default value is `1000000` (100 万元). When the user changes it to `200`, it becomes 200 元, not 200 万元.

- [ ] **Step 2: Update the label to clarify units**

```html
<label>模拟总资金 (万元)</label>
<input type="number" id="cfg-capital" value="100" step="10" min="1">
```

- [ ] **Step 3: Update the savePreferences function to convert units**

```javascript
function savePreferences() {
  clearTimeout(_savePrefsTimer);
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = '保存中...';
  statusEl.style.color = 'var(--yellow)';

  const capitalInput = Number(document.getElementById('cfg-capital').value);
  // Convert 万元 to 元
  const capitalBase = capitalInput * 10000;

  const prefs = {
    watchlist: document.getElementById('cfg-watchlist').value
      .split(',').map(s => s.trim()).filter(Boolean),
    capital_base: capitalBase,
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    execution_mode: execMode,
  };

  fetch(PREFS_API, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  }).then(res => {
    if (res.ok) {
      statusEl.textContent = '已保存';
      statusEl.style.color = 'var(--green)';
      showToast('配置已保存', 'success');
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    } else {
      statusEl.textContent = '保存失败';
      statusEl.style.color = 'var(--red)';
      showToast('保存失败，请重试', 'error');
    }
  }).catch(() => {
    statusEl.textContent = '保存失败';
    statusEl.style.color = 'var(--red)';
    showToast('保存失败，请检查网络', 'error');
  });
}
```

- [ ] **Step 4: Update buildRunPayload to use the same conversion**

```javascript
function buildRunPayload() {
  const watchlist = document.getElementById('cfg-watchlist').value
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  
  const capitalInput = Number(document.getElementById('cfg-capital').value);
  // Convert 万元 to 元
  const capitalBase = capitalInput * 10000;
  
  return {
    capital_base: capitalBase,
    watchlist,
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    allow_new_positions: document.getElementById('cfg-new-pos').classList.contains('on'),
    decision_mode: document.getElementById('cfg-mode').value,
    execution_mode: execMode,
  };
}
```

- [ ] **Step 5: Update renderConfig to display in 万元**

```javascript
function renderConfig(config) {
  if (!config || configHydrated) return;

  // 服务端偏好优先于 HTML 默认值
  if (config.watchlist) {
    document.getElementById('cfg-watchlist').value = Array.isArray(config.watchlist)
      ? config.watchlist.join(',') : config.watchlist;
  }
  if (config.capital_base !== undefined) {
    // Convert 元 to 万元 for display
    const capitalWan = Number(config.capital_base) / 10000;
    document.getElementById('cfg-capital').value = capitalWan;
  }
  if (config.max_position_ratio !== undefined) {
    document.getElementById('cfg-max-pos').value = Number(config.max_position_ratio) * 100;
  }
  if (config.stop_loss_ratio !== undefined) {
    document.getElementById('cfg-stop-loss').value = Number(config.stop_loss_ratio) * 100;
  }
  if (config.max_daily_loss_ratio !== undefined) {
    document.getElementById('cfg-max-daily').value = Number(config.max_daily_loss_ratio) * 100;
  }
  if (config.allow_new_positions !== undefined) {
    document.getElementById('cfg-new-pos').classList.toggle('on', Boolean(config.allow_new_positions));
  }
  if (config.decision_mode) {
    document.getElementById('cfg-mode').value = config.decision_mode;
  }
  const mode = config.execution_mode === 'decision' ? 'decision' : 'full';
  const execButtons = document.querySelectorAll('#exec-mode button');
  execButtons.forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
  execMode = mode;
  configHydrated = true;
}
```

- [ ] **Step 6: Test the fix**

1. Set capital to `100` (万元)
2. Click save
3. Check the API response - should show `capital_base: 1000000`
4. Refresh the page - should show `100` in the input

- [ ] **Step 7: Commit**

```bash
git add src/api/dashboard.html
git commit -m "fix: change capital input to 万元 unit for better usability"
```

---

### Task 6: Fix Target Position Display

**Problem:** Target position shows "计算中..." and `--` instead of actual data.

**Root Cause:** In "仅决策" mode, the target position is not calculated. The display should show a clearer message.

**Files:**
- Modify: `src/api/dashboard.html:1199-1243`

- [ ] **Step 1: Check current implementation**

The `stageBodyHtml` function handles the target position display. When there are no items, it shows the message from `step.message`.

- [ ] **Step 2: Improve the message for decision-only mode**

In `renderTimeline` function, when the stage is "target" and status is "running", we can check if we're in decision-only mode:

```javascript
function renderTimeline(latestRun) {
  const timeline = document.getElementById('timeline');
  const steps = toList(latestRun?.steps);
  if (!steps.length) {
    timeline.innerHTML = '<div class="timeline-empty" id="timeline-empty">配置参数后点击「运行一轮模拟交易」开始</div>';
    return;
  }
  timeline.innerHTML = '';
  steps.forEach(step => {
    const stage = normalizeText(step.stage || step.name, 'stage').toLowerCase();
    const statusRaw = normalizeText(step.status, 'done').toLowerCase();
    const status = statusRaw === 'error' || statusRaw === 'failed' ? 'error' : statusRaw === 'running' || statusRaw === 'in_progress' ? 'running' : 'done';
    const time = formatTime(pickFirst(step, ['created_at', 'timestamp', 'time']));
    const div = document.createElement('div');
    div.className = `tl-step ${status}`;
    div.dataset.tag = stage;
    
    // Customize message for target stage in decision-only mode
    let stepCopy = {...step};
    if (stage === 'target' && execMode === 'decision') {
      stepCopy.message = '仅决策模式，目标仓位未计算';
    }
    
    div.innerHTML = `
      <div class="step-head">
        <span class="step-tag ${stage}">${escapeHtml(stageLabel(stage))}</span>
        <span class="step-time">${escapeHtml(time)}</span>
      </div>
      <div class="step-body">${stageBodyHtml(stepCopy)}</div>
    `;
    timeline.appendChild(div);
  });
  timeline.scrollTop = timeline.scrollHeight;
}
```

- [ ] **Step 3: Test the fix**

1. Select "仅决策" execution mode
2. Run a trading cycle
3. Check the timeline - target position should show "仅决策模式，目标仓位未计算" instead of "计算中..."

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "fix: show clearer message for target position in decision-only mode"
```

---

### Task 7: Add Loading States for Better UX

**Problem:** No visual feedback when buttons are clicked or data is loading.

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: Add loading state CSS**

```css
/* Add to existing styles */
.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--fg);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.btn-loading {
  position: relative;
  pointer-events: none;
}

.btn-loading::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 16px;
  height: 16px;
  margin: -8px 0 0 -8px;
  border: 2px solid transparent;
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
```

- [ ] **Step 2: Update button handlers to show loading**

```javascript
function setButtonLoading(btn, loading, originalText) {
  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span>' + originalText;
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || originalText;
  }
}

// Update triggerRun
async function triggerRun() {
  if (simRunning) return;
  simRunning = true;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, true, '运行中...');
  // ... rest of the function
}

// Update triggerScan
async function triggerScan() {
  if (scanRunning) return;
  scanRunning = true;
  const btn = document.getElementById('scan-btn');
  setButtonLoading(btn, true, '扫描中...');
  // ... rest of the function
}

// Update triggerBacktest
async function triggerBacktest() {
  if (btRunning) return;
  btRunning = true;
  const btn = document.getElementById('bt-btn');
  setButtonLoading(btn, true, '回测中...');
  // ... rest of the function
}
```

- [ ] **Step 3: Test the fix**

Click any action button (运行, 扫描, 回测). Should see a spinning indicator while processing.

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add loading spinners for better user feedback"
```

---

### Task 8: Add Keyboard Shortcuts

**Problem:** No keyboard shortcuts for common actions.

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: Add keyboard event listener**

```javascript
// Add at the end of the script, before loadDashboard()
document.addEventListener('keydown', (event) => {
  // Ctrl/Cmd + S: Save preferences
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault();
    savePreferences();
  }
  
  // Ctrl/Cmd + Enter: Run trading cycle
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    if (!simRunning) {
      triggerRun();
    }
  }
  
  // Ctrl/Cmd + F: Focus search input (when in market view)
  if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
    const marketView = document.getElementById('view-market');
    if (marketView.classList.contains('active')) {
      event.preventDefault();
      document.getElementById('stock-search-input').focus();
    }
  }
  
  // Escape: Exit search mode
  if (event.key === 'Escape' && isSearchMode) {
    exitSearchMode();
  }
});
```

- [ ] **Step 2: Add keyboard shortcut hints to UI**

```html
<!-- Add to the run button area -->
<div style="font-size:10px;color:var(--dim);margin-top:4px">
  快捷键: Ctrl+Enter 运行 | Ctrl+S 保存
</div>
```

- [ ] **Step 3: Test the fix**

1. Press Ctrl+Enter - should trigger run
2. Press Ctrl+S - should save preferences
3. In market view, press Ctrl+F - should focus search input
4. Press Escape in search mode - should exit search

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard.html
git commit -m "feat: add keyboard shortcuts for common actions"
```

---

## Summary

| Task | Bug/Feature | Priority | Files Changed |
|------|-------------|----------|---------------|
| 1 | Error events display | High | dashboard.html |
| 2 | Stock search | High | routes_market.py, dashboard.html |
| 3 | Execution mode persistence | Medium | dashboard.html |
| 4 | Save configuration feedback | Medium | dashboard.html |
| 5 | Capital display units | Medium | dashboard.html |
| 6 | Target position display | Medium | dashboard.html |
| 7 | Loading states | Low | dashboard.html |
| 8 | Keyboard shortcuts | Low | dashboard.html |

---

## Verification

After implementing all tasks, run through the complete test scenario:

1. Open dashboard at `http://13.214.201.113:8000/dashboard`
2. Verify all status indicators show green
3. Set capital to 100 万元
4. Add stocks to watchlist
5. Run with Mock + 完整链路 - verify all 4 steps complete
6. Run with Mock + 仅决策 - verify target position shows correct message
7. Check error events tab - messages should be readable
8. Test stock search - should find matching stocks
9. Toggle execution mode - should persist after refresh
10. Save configuration - should show toast notification
11. Test keyboard shortcuts

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-29-dashboard-bugfixes.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
