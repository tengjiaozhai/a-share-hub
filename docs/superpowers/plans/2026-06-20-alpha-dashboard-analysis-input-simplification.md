# Alpha Dashboard Analysis Input Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Alpha dashboard's manual fill entry flow with a simpler analysis input flow that keeps generic symbol analysis, adds `position_ratio` and `buy_time`, and removes `ticket/operator` from the main dashboard path.

**Architecture:** Keep the existing `/api/v1/alpha/portfolio/report` endpoint as the single analysis entrypoint, but extend its request/response contract to carry explicit analysis inputs. On the UI side, keep the current Alpha report card as the canonical entry, add the new fields there, remove the manual-fill form block entirely, and render the returned analysis context inside the report instead of routing users through suggestion-ticket execution metadata.

**Tech Stack:** FastAPI, Pydantic, server-rendered HTML partials, vanilla JavaScript, pytest

---

## File Structure

- Modify: `a-share-hub/src/api/dashboard_page/partials/view_alpha.html`
  - Replace the report-card copy and controls so the Alpha page exposes `symbol + position_ratio + buy_time` in one place.
  - Remove the `alpha-fill-form` block from the rendered dashboard HTML.
- Modify: `a-share-hub/src/api/dashboard_page/scripts/alpha.js`
  - Send the new analysis inputs to `/api/v1/alpha/portfolio/report`.
  - Render returned analysis context in the report body.
  - Remove only the JS helpers that become dead because `alpha-fill-form` is deleted.
- Modify: `a-share-hub/src/api/routes_alpha.py`
  - Extend `GeneratePortfolioReportRequest` with the new analysis input fields.
  - Keep `/api/v1/alpha/portfolio/report` as the single analysis endpoint.
- Modify: `a-share-hub/src/alpha/report_service.py`
  - Normalize and return the new analysis input contract.
  - Attach analysis context to each requested symbol so the UI can show what was analyzed.
- Modify: `a-share-hub/tests/test_dashboard_alpha_tab.py`
  - Update Alpha page contract tests to require the new inputs and forbid the deleted manual-fill UI.
- Modify: `a-share-hub/tests/test_dashboard_page_contract.py`
  - Update rendered HTML contract markers for the Alpha analysis card.
- Modify: `a-share-hub/tests/test_alpha_routes.py`
  - Add/adjust route tests so `/api/v1/alpha/portfolio/report` accepts and forwards `position_ratio` / `buy_time`.
- Modify: `a-share-hub/docs/runbooks/alpha-desk.md`
  - Update the user-facing runbook so the dashboard path is described as analysis-first, not manual-fill-first.

---

### Task 1: Lock the New Alpha Dashboard HTML Contract

**Files:**
- Modify: `a-share-hub/tests/test_dashboard_alpha_tab.py`
- Modify: `a-share-hub/tests/test_dashboard_page_contract.py`
- Test: `a-share-hub/tests/test_dashboard_alpha_tab.py`
- Test: `a-share-hub/tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write the failing Alpha tab contract test**

```python
def test_dashboard_contains_code_analysis_first_controls(_patch_auth):
    html = _dashboard_html()
    assert 'id="alpha-report-symbol"' in html
    assert 'id="alpha-report-position-ratio"' in html
    assert 'id="alpha-report-buy-time"' in html
    assert 'id="alpha-report-generate"' in html
    assert "股票代码" in html
    assert "持仓仓位 (%)" in html
    assert "买入时间" in html
    assert "分析股票" in html


def test_dashboard_removes_alpha_manual_fill_entry_ui(_patch_auth):
    html = _dashboard_html()
    assert 'id="alpha-fill-form"' not in html
    assert 'id="alpha-fill-ticket"' not in html
    assert 'id="alpha-fill-operator"' not in html
    assert "手动回填成交" not in html
```

- [ ] **Step 2: Run the targeted dashboard Alpha tab test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py -q
```

Expected: FAIL because the current HTML still contains `alpha-fill-form` and does not contain `alpha-report-position-ratio` / `alpha-report-buy-time`.

- [ ] **Step 3: Write the failing rendered page contract update**

```python
def test_render_dashboard_html_contains_alpha_contract():
    html = render_dashboard_html()
    assert "view-alpha" in html
    assert 'id="alpha-report-symbol"' in html
    assert 'id="alpha-report-position-ratio"' in html
    assert 'id="alpha-report-buy-time"' in html
    assert "分析股票" in html
    assert 'id="alpha-fill-form"' not in html
    assert 'id="alpha-fill-ticket"' not in html
    assert 'id="alpha-fill-operator"' not in html
```

- [ ] **Step 4: Run the rendered page contract test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_alpha_contract -q
```

Expected: FAIL because the renderer still outputs the removed manual-fill block and misses the two new analysis inputs.

- [ ] **Step 5: Commit the red tests**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && git add tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py && git commit -m "test: lock alpha dashboard analysis input contract"
```

---

### Task 2: Extend the Report API Contract for Analysis Inputs

**Files:**
- Modify: `a-share-hub/src/api/routes_alpha.py`
- Modify: `a-share-hub/src/alpha/report_service.py`
- Modify: `a-share-hub/tests/test_alpha_routes.py`
- Test: `a-share-hub/tests/test_alpha_routes.py`

- [ ] **Step 1: Write the failing route test for the new report payload**

```python
def test_generate_portfolio_report_endpoint_forwards_analysis_inputs(
    authenticated_client,
    test_app,
    monkeypatch,
):
    captured_payload = {}

    class FakeReportService:
        def __init__(self, store, user_id=None):
            self.store = store
            self.user_id = user_id

        def generate_report(self, payload):
            captured_payload.update(payload)
            return {
                "generated_at": "2026-06-20T12:00:00+08:00",
                "portfolio_snapshot": {},
                "analysis_input": {
                    "symbols": payload["symbols"],
                    "position_ratio": payload["position_ratio"],
                    "buy_time": payload["buy_time"],
                },
                "backtest_window": payload["backtest_window"],
                "items": [],
            }

    monkeypatch.setattr(routes_alpha, "AlphaPortfolioReportService", FakeReportService)

    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report",
        json={
            "symbols": ["MU"],
            "position_ratio": 35.0,
            "buy_time": "2026-06-20T09:30",
            "include_shadow": True,
            "include_backtest": True,
            "backtest_window": "60d",
            "opening_cash": 10000.0,
        },
    )

    assert response.status_code == 200
    assert captured_payload["symbols"] == ["MU.US"]
    assert captured_payload["position_ratio"] == 35.0
    assert captured_payload["buy_time"] == "2026-06-20T09:30"
```

- [ ] **Step 2: Run the targeted route test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_generate_portfolio_report_endpoint_forwards_analysis_inputs -q
```

Expected: FAIL because `GeneratePortfolioReportRequest` does not currently accept `position_ratio` or `buy_time`.

- [ ] **Step 3: Implement the minimal route and report-service contract**

```python
class GeneratePortfolioReportRequest(BaseModel):
    symbols: list[str] = []
    position_ratio: float | None = None
    buy_time: str | None = None
    include_shadow: bool = True
    include_backtest: bool = True
    backtest_window: str = "60d"
    opening_cash: float = 10_000.0
```

```python
def generate_report(self, payload: dict) -> dict:
    symbols = normalize_report_symbols(payload.get("symbols") or [])
    position_ratio = payload.get("position_ratio")
    buy_time = payload.get("buy_time")
    analysis_input = {
        "symbols": symbols,
        "position_ratio": position_ratio,
        "buy_time": buy_time,
    }
    ...
    items.append(
        {
            **position_section,
            "analysis_context": {
                "position_ratio": position_ratio,
                "buy_time": buy_time,
            } if symbols and symbol in symbols else {},
            "fill_summary": fill_summary,
            "shadow": shadow,
            "backtest": backtest,
            "recommendation": recommendation,
        }
    )
    return {
        "generated_at": datetime.now(UTC).astimezone().isoformat(),
        "portfolio_snapshot": snapshot or {},
        "analysis_input": analysis_input,
        "backtest_window": backtest_window,
        "items": items,
    }
```

- [ ] **Step 4: Run the Alpha route tests to verify the contract passes**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py -q
```

Expected: PASS, including the new payload-forwarding test and the existing symbol-normalization test.

- [ ] **Step 5: Commit the backend contract change**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && git add src/api/routes_alpha.py src/alpha/report_service.py tests/test_alpha_routes.py && git commit -m "feat: add alpha analysis input report contract"
```

---

### Task 3: Replace the Dashboard Manual-Fill UI with Analysis Inputs

**Files:**
- Modify: `a-share-hub/src/api/dashboard_page/partials/view_alpha.html`
- Modify: `a-share-hub/src/api/dashboard_page/scripts/alpha.js`
- Test: `a-share-hub/tests/test_dashboard_alpha_tab.py`
- Test: `a-share-hub/tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Implement the minimal Alpha page markup change**

```html
<div class="alpha-report-toolbar">
  <div class="alpha-field alpha-report-symbol-field">
    <label for="alpha-report-symbol">股票代码</label>
    <input id="alpha-report-symbol" placeholder="如 MU / 600519 / 000001.SZ / 多个代码用逗号分隔" />
  </div>
  <div class="alpha-field">
    <label for="alpha-report-position-ratio">持仓仓位 (%)</label>
    <input id="alpha-report-position-ratio" type="number" min="0" max="100" step="0.01" placeholder="如 35" />
  </div>
  <div class="alpha-field">
    <label for="alpha-report-buy-time">买入时间</label>
    <input id="alpha-report-buy-time" type="datetime-local" />
  </div>
  <button type="button" id="alpha-report-generate" class="run-btn accent alpha-report-trigger">
    分析股票
  </button>
</div>
```

```html
<!-- Delete the entire alpha-panel-fill-form article -->
```

- [ ] **Step 2: Run the HTML contract tests to verify only markup-related failures remain**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: FAIL in JavaScript contract/render behavior if `alpha.js` still expects only the old payload shape.

- [ ] **Step 3: Implement the minimal JavaScript payload and rendering update**

```javascript
async function loadAlphaReport() {
  const requestedSymbols = resolveAlphaReportSymbols();
  const ratioInput = document.getElementById('alpha-report-position-ratio');
  const buyTimeInput = document.getElementById('alpha-report-buy-time');
  const payload = {
    symbols: requestedSymbols,
    position_ratio: ratioInput?.value === '' ? null : Number(ratioInput?.value),
    buy_time: buyTimeInput?.value || null,
    include_shadow: shadowToggle?.checked !== false,
    include_backtest: backtestToggle?.checked !== false,
    backtest_window: windowSelect?.value || '60d',
    opening_cash: 10000,
  };
  ...
}
```

```javascript
function renderAlphaReport(report, requestedSymbols = []) {
  ...
  const analysisContext = item.analysis_context || {};
  const ratioText = analysisContext.position_ratio == null ? '--' : `${formatNumber(analysisContext.position_ratio, 2)}%`;
  const buyTimeText = normalizeText(analysisContext.buy_time, '--');
  return `<div class="alpha-report-item" data-symbol="${escapeHtml(symbol)}">
    ...
    <div class="alpha-report-grid">
      <span class="alpha-report-grid-label">输入仓位</span><span class="alpha-report-grid-value">${escapeHtml(ratioText)}</span>
      <span class="alpha-report-grid-label">买入时间</span><span class="alpha-report-grid-value">${escapeHtml(buyTimeText)}</span>
    </div>
    ...
  </div>`;
}
```

```javascript
// Delete only these fill-form-specific helpers because the form no longer exists:
// submitAlphaManualFill
// populateAlphaFillTicketSelect
// handleAlphaFillTicketChange
```

- [ ] **Step 4: Run the dashboard Alpha tests to verify the page contract is green**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: PASS, with no remaining references to `alpha-fill-form`, `alpha-fill-ticket`, or `alpha-fill-operator` in the rendered dashboard HTML.

- [ ] **Step 5: Commit the frontend simplification**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && git add src/api/dashboard_page/partials/view_alpha.html src/api/dashboard_page/scripts/alpha.js tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py && git commit -m "feat: simplify alpha dashboard analysis inputs"
```

---

### Task 4: Update the Runbook and Verify the End-to-End Contract

**Files:**
- Modify: `a-share-hub/docs/runbooks/alpha-desk.md`
- Test: `a-share-hub/tests/test_alpha_routes.py`
- Test: `a-share-hub/tests/test_dashboard_alpha_tab.py`
- Test: `a-share-hub/tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Update the Alpha desk runbook wording**

```md
## 概述

Alpha 操作台当前以持仓分析为主。Dashboard 中的 Alpha 页提供通用股票代码分析入口，并允许用户直接补充 `持仓仓位 (%)` 与 `买入时间` 作为分析上下文。

Dashboard 不再提供“建议单 + 操作员 + 手动回填成交”的主入口；历史成交与 multi-leg 数据仅保留为只读参考信息。
```

```md
### 持仓分析报告

```
POST /api/v1/alpha/portfolio/report
```

请求体支持：
- `symbols`
- `position_ratio`
- `buy_time`
- `include_shadow`
- `include_backtest`
- `backtest_window`
- `opening_cash`
```

- [ ] **Step 2: Run the focused regression suite**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_dashboard_alpha_tab.py \
  tests/test_dashboard_page_contract.py \
  tests/test_alpha_routes.py -q
```

Expected: PASS across the dashboard HTML contract and the Alpha report route contract.

- [ ] **Step 3: Run a minimal rendered-dashboard smoke check**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py::test_dashboard_contains_code_analysis_first_controls -q
```

Expected: PASS, confirming the shipped dashboard HTML exposes the generic analysis inputs.

- [ ] **Step 4: Review for orphaned manual-fill references created by this change**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && rg -n "alpha-fill-form|alpha-fill-ticket|alpha-fill-operator|submitAlphaManualFill|handleAlphaFillTicketChange" src tests docs
```

Expected: no matches in `src/api/dashboard_page` or dashboard-facing tests/docs; any remaining hits outside the dashboard path must be consciously retained or removed before merge.

- [ ] **Step 5: Commit docs and verification**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && git add docs/runbooks/alpha-desk.md && git commit -m "docs: align alpha desk runbook with analysis-first dashboard"
```

---

## Self-Review

- Spec coverage: the plan covers the user-confirmed scope of keeping generic symbol analysis, directly deleting the dashboard manual-fill entry, and replacing it with `position_ratio + buy_time` on the same analysis card.
- Placeholder scan: no `TODO`, `TBD`, or “write tests for the above” placeholders remain.
- Type consistency: the same field names are used throughout the plan: `position_ratio`, `buy_time`, and `analysis_context`.
