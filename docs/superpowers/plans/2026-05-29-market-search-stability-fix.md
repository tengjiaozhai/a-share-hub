# 市场搜索稳定性修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/api/v1/market/stocks` 在 AkShare 目录刷新临时为空时继续保留最后一次有效股票池，并让实时行情搜索在无命中时清空旧表，避免用户看到旧数据和误判。

**Architecture:** 继续使用现有 `StockCatalogCache` 作为唯一股票目录入口，但把“空刷新”视为非权威结果：只有非空结果才能覆盖 `_frame` 和 `_expires_at`。`dashboard.html` 的搜索逻辑在无命中时要主动清空行情表、重置搜索状态并渲染一个明确的空态，而不是保留上一次的行情行。这样后端不会被一次临时上游故障冻成空目录，前端也不会把旧结果伪装成当前查询结果。

**Tech Stack:** Python 3.11, FastAPI, pandas, pytest, HTML/CSS/JavaScript

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `src/data/providers/akshare_catalog.py:46-73` | Modify | Keep the last non-empty catalog snapshot and avoid caching empty refreshes |
| `tests/test_akshare_catalog.py:1-48` | Modify | Lock the cache behavior for non-empty refresh, empty refresh, and cold-start empty fetch |
| `src/api/dashboard.html:911-963` | Modify | Clear stale market rows and reset search state when a query returns no matches |
| `tests/test_dashboard_market_tab.py:1-10` | Modify | Assert the dashboard source contains the no-match empty-state branch |

## Scope

- Do not add a second stock source, a new config flag, or a new persistence layer.
- Do not touch scan, backtest, or order execution code.
- Do not change the `/api/v1/market/stocks` response shape.

### Task 1: Stop empty stock catalog refreshes from poisoning the cache

**Files:**
- Modify: `src/data/providers/akshare_catalog.py:46-73`
- Modify: `tests/test_akshare_catalog.py:1-48`

- [ ] **Step 1: Write the failing cache regression tests**

Add two tests to `tests/test_akshare_catalog.py`:

```python
from datetime import datetime, timedelta


def test_catalog_cache_keeps_last_good_frame_when_refresh_returns_empty():
    cache = StockCatalogCache(ttl_seconds=0)
    cache._frame = pd.DataFrame([
        {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
    ])
    cache._expires_at = datetime.utcnow() - timedelta(seconds=1)

    frame = cache.load(lambda: pd.DataFrame(columns=["code", "name"]))

    assert frame.to_dict("records") == [
        {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
    ]
    assert cache._frame.to_dict("records") == [
        {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
    ]


def test_catalog_cache_does_not_promote_empty_first_fetch_to_cached_state():
    cache = StockCatalogCache(ttl_seconds=0)

    frame = cache.load(lambda: pd.DataFrame(columns=["code", "name"]))

    assert frame.empty
    assert cache._frame is None
```

- [ ] **Step 2: Run the catalog tests and confirm they fail**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_catalog.py -v`

Expected: at least one failure because `load()` currently caches the empty frame.

- [ ] **Step 3: Change `StockCatalogCache.load()` to keep the last good frame**

Implement the minimal branch in `src/data/providers/akshare_catalog.py`:

```python
frame = normalize_stock_list_frame(fetcher())
if frame.empty:
    if self._frame is not None:
        return self._frame
    return frame
self._frame = frame
self._expires_at = now + timedelta(seconds=self.ttl_seconds)
return frame
```

Do not set `_frame` or `_expires_at` when the refresh result is empty.

- [ ] **Step 4: Re-run the catalog tests and the API smoke test**

Run:
- `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_catalog.py tests/test_market_stock_list_api.py -v`

Expected:
- `tests/test_akshare_catalog.py` passes
- `/api/v1/market/stocks` still filters correctly through the existing route test

- [ ] **Step 5: Commit the backend fix**

```bash
git add src/data/providers/akshare_catalog.py tests/test_akshare_catalog.py
git commit -m "fix: keep last good stock catalog snapshot"
```

### Task 2: Clear the market table when a search returns no matches

**Files:**
- Modify: `src/api/dashboard.html:911-963`
- Modify: `tests/test_dashboard_market_tab.py:1-10`

- [ ] **Step 1: Write the failing dashboard source assertion**

Extend `tests/test_dashboard_market_tab.py` with an assertion that the no-match branch exists:

```python
from pathlib import Path


def test_dashboard_search_clears_stale_rows_on_no_match():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "暂无匹配结果" in content
```

- [ ] **Step 2: Run the dashboard source test and confirm it fails**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_market_tab.py -v`

Expected: fail until the no-match branch is added.

- [ ] **Step 3: Update `searchStock()` to clear stale rows**

In `src/api/dashboard.html`, replace the `searchResults.length === 0` branch with:

```javascript
if (searchResults.length === 0) {
  statusEl.textContent = '未找到匹配的股票';
  statusEl.style.color = 'var(--yellow)';
  searchResults = [];
  selectedSearchIndex = -1;
  isSearchMode = false;
  document.getElementById('tb-market-full').innerHTML =
    '<tr><td colspan="12" class="market-empty">暂无匹配结果</td></tr>';
  return;
}
```

Do not leave the previous quote table in place after a zero-result search.

- [ ] **Step 4: Re-run the dashboard source test and a live browser smoke check**

Run:
- `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_market_tab.py -v`

Then open the dashboard, search `000858`, then `贵州茅台`, and verify the table no longer keeps the old rows after a miss.

- [ ] **Step 5: Commit the dashboard fix**

```bash
git add src/api/dashboard.html tests/test_dashboard_market_tab.py
git commit -m "fix: clear stale market rows on empty search"
```

## Acceptance Criteria

- A temporary empty response from AkShare no longer freezes `/api/v1/market/stocks` at `[]` for the whole TTL window.
- A cold-start empty catalog does not get promoted into a fresh cached snapshot.
- Searching an unknown stock in the market tab clears the quote table instead of leaving stale rows visible.
- `pytest tests/test_akshare_catalog.py tests/test_market_stock_list_api.py tests/test_dashboard_market_tab.py -v` passes.
- A browser smoke test on the dashboard shows valid searches still work after a miss.
