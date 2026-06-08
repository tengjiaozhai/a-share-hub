# Dashboard Control Room and Data Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the dashboard into a dense market-terminal control room and wire it to stable dashboard, performance, automation, and history APIs backed by the paper-ledger and scheduler state.

**Architecture:** One dashboard shell, one contract-first data layer, one canonical paper-ledger for auto/manual summaries. The front end should feel like an industrial control room: dark neutral base, sharp semantic accents, tabular numerals, compact cards, and no marketing-style hero composition. The page boots with a minimal summary payload, then hydrates performance, automation, and history panels from dedicated endpoints keyed by `market` and `account_kind`.

**Tech Stack:** FastAPI, Jinja-rendered HTML, vanilla CSS/JS, SQLAlchemy, APScheduler, PostgreSQL, pytest, browser QA

---

## File Structure

| File | Responsibility |
|---|---|
| `src/api/routes_dashboard.py` | Dashboard read/write endpoints, payload assembly, and market/account routing |
| `src/api/dashboard_page/partials/view_dashboard.html` | New control-room layout and DOM hooks |
| `src/api/dashboard_page/styles/dashboard.css` | Layout grid, typography tokens, chart containers, responsive behavior |
| `src/api/dashboard_page/scripts/dashboard.js` | Page bootstrap, fetch orchestration, chart rendering, market/range switching |
| `src/api/dashboard_contracts.py` | Pydantic response models for workbench, performance, automation, history, alerts |
| `src/paper_ledger/models.py` | Add provenance fields needed for curves, seeded history, and run attribution |
| `src/paper_ledger/store.py` | Query helpers for nav curves, comparison windows, run history, and per-market summaries |
| `src/paper_ledger/backfill.py` | Backfill provenance and run bookkeeping for seeded history |
| `src/scheduler/daily_scheduler.py` | Daily job registration, next-run lookup, and one-run-per-day guard |
| `src/main.py` | Scheduler lifecycle and startup backfill ordering |
| `alembic/versions/20260607_000009_add_paper_nav_daily_provenance.py` | Migration for `paper_nav_daily` provenance fields |
| `tests/test_dashboard_api.py` | API contract tests for summary, performance, automation, and history payloads |
| `tests/test_dashboard_performance.py` | Return, drawdown, and comparison-window calculation tests |
| `tests/test_dashboard_page_contract.py` | DOM contract and legacy-marker tests |
| `tests/test_daily_scheduler.py` | Scheduler existence, job timing, and next-run behavior |
| `tests/test_paper_ledger_store.py` | Ledger history/query helper tests |
| `tests/test_paper_ledger_backfill.py` | Backfill provenance and skip behavior |

---

## Phase 1: Control-Room Shell And Visual System

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**Objective:** Turn the dashboard into a control room rather than a generic SaaS page. The layout should be dense, readable, and operational: top status rail, left command rail, center performance stack, right automation/risk rail, bottom history ledger.

- [ ] **Step 1: Replace the current column layout with the new information architecture**

```html
<!-- New high-level regions -->
<header class="dashboard-rail dashboard-rail--top">...</header>
<aside class="dashboard-rail dashboard-rail--left">...</aside>
<main class="dashboard-core">...</main>
<aside class="dashboard-rail dashboard-rail--right">...</aside>
<section class="dashboard-ledger">...</section>
```

- [ ] **Step 2: Define the visual system with explicit design tokens**

```css
:root {
  --bg: #0b1117;
  --panel: #101922;
  --panel-2: #0e1520;
  --text: #e7edf5;
  --muted: #94a3b8;
  --accent: #4dd4c6;
  --warn: #f7b955;
  --danger: #f26d6d;
  --radius: 8px;
  --stroke: rgba(255, 255, 255, 0.08);
}
```

Use a utilitarian, industrial direction. Avoid purple gradients, oversized hero sections, and card-heavy marketing composition. Keep spacing compact, use tabular numerals for KPI blocks, and make semantic status colors carry meaning.

- [ ] **Step 3: Add the dashboard placeholders the JS will bind to**

The HTML should expose stable IDs for:

- automation status
- performance summary
- NAV curve canvas or SVG
- fixed comparison windows `7D / 30D / 90D / YTD`
- recent auto runs
- manual sandbox runs
- alerts and stale-data warnings

- [ ] **Step 4: Wire responsive breakpoints**

The desktop layout should be a three-column terminal. Tablet should collapse to two columns. Mobile should become a single stack with the status rail pinned first, then performance, automation, and history.

**Acceptance Criteria:**

- Desktop at 1440px and 1024px shows all panels without overlap or clipped labels.
- Mobile at 390px stacks the panels cleanly and keeps the primary actions visible.
- The dashboard copy uses the new terms `自动运行状态`, `净值曲线`, `区间表现对比`, `最近运行记录`.
- No legacy-facing copy like `本轮运行` or `历史对比` remains in the rendered shell.

---

## Phase 2: Contract-First Dashboard APIs

**Files:**
- Create: `src/api/dashboard_contracts.py`
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/paper_ledger/models.py`
- Modify: `src/paper_ledger/store.py`
- Create: `alembic/versions/20260607_000009_add_paper_nav_daily_provenance.py`

**Objective:** Split the dashboard data into stable, named payloads so the page can refresh each panel independently without guessing at dict shapes.

- [ ] **Step 1: Define the API contracts**

```python
class DashboardServicesPayload(BaseModel):
    database: str
    llm: str
    market_data: str


class DashboardRiskPayload(BaseModel):
    active_target_count: int
    open_orders: int
    broker_event_count: int
    healthy: bool
    daily_pnl: float


class DashboardAutomationPayload(BaseModel):
    today_status: str
    last_run_at: str | None
    next_run_at: str | None


class DashboardPerformancePayload(BaseModel):
    today_return: float
    month_return: float
    max_drawdown: float
    nav_curve: list[dict]
    comparison_cards: list[dict]


class DashboardHistoryPayload(BaseModel):
    auto_runs: list[dict]
    manual_runs: list[dict]
    fills: list[dict]
    decisions: list[dict]


class DashboardAlertPayload(BaseModel):
    level: str
    code: str
    message: str


class DashboardWorkbenchPayload(BaseModel):
    market: str
    account_kind: str
    services: DashboardServicesPayload
    risk: DashboardRiskPayload
    automation: DashboardAutomationPayload
    performance: DashboardPerformancePayload
    history: DashboardHistoryPayload
    alerts: list[DashboardAlertPayload]
```

The contract should explicitly carry:

- `market`
- `account_kind`
- `services`
- `services.database`
- `services.llm`
- `services.market_data`
- `risk`
- `automation.today_status`
- `automation.last_run_at`
- `automation.next_run_at`
- `performance.today_return`
- `performance.month_return`
- `performance.max_drawdown`
- `performance.nav_curve`
- `performance.comparison_cards`
- `history.auto_runs`
- `history.manual_runs`
- `history.fills`
- `history.decisions`
- `alerts`

- [ ] **Step 2: Expose a small endpoint suite instead of one oversized blob**

The page should use these read/write endpoints:

- `GET /api/v1/dashboard/workbench?market=a&account_kind=auto`
- `GET /api/v1/dashboard/performance?market=a&account_kind=auto&window=30d`
- `GET /api/v1/dashboard/automation?market=a&account_kind=auto`
- `GET /api/v1/dashboard/history?market=a&account_kind=auto&source=all&limit=20`
- `POST /api/v1/dashboard/run` for the manual sandbox only

`source` should accept `auto`, `manual`, or `all`, with `all` as the default so the dashboard can render both lanes from the same endpoint family.
`POST /api/v1/dashboard/run` should continue to accept the current watchlist and sizing config, but the backend must stamp the run as `account_kind=manual` and `source=manual` before it touches the paper-ledger tables.

The workbench bootstrap should still return a compact summary, but the chart and history panels should load from dedicated endpoints so the page can refresh them independently.

- [ ] **Step 3: Extend the paper-ledger schema for provenance**

`paper_nav_daily` needs to know where the row came from so the UI can distinguish real auto runs from seeded history. Add explicit provenance fields, at minimum:

- `run_id`
- `source` with values `auto`, `manual`, `backfill`

If a row is seeded, the dashboard should be able to label it as historical backfill rather than pretending it is live performance.

- [ ] **Step 4: Add ledger helpers for ranges and comparison windows**

`src/paper_ledger/store.py` should expose helpers for:

- latest run by `market` and `account_kind`
- nav history by `account_id`, `start`, `end`, and `limit`
- comparison windows for `7d`, `30d`, `90d`, and `ytd`
- run history filtered by `source`

**Acceptance Criteria:**

- The dashboard API responses have pinned top-level keys and nested payload names.
- The same schema works for A 股 and 美股 without branchy frontend code.
- Auto, manual, and backfill rows are distinguishable in the ledger.
- Tests can assert the shape of the API without depending on implementation details.

---

## Phase 3: Scheduler And Ledger Execution Wiring

**Files:**
- Modify: `src/scheduler/daily_scheduler.py`
- Modify: `src/main.py`
- Modify: `src/paper_ledger/backfill.py`

**Objective:** Make automatic daily runs predictable, queryable, and restart-safe. The scheduler should be visible to the dashboard, and the startup backfill should fill enough history for the curve and comparison cards to render immediately.

- [ ] **Step 1: Make scheduler state observable without reaching into private fields**

Expose public helpers for:

- `next_run_at(market)`
- `job_status(market)`
- `has_job(market)`

Do not let the dashboard read `scheduler._scheduler` directly.

- [ ] **Step 2: Keep the one-run-per-day guard inside the scheduler or ledger layer**

The guard should prevent a second successful auto run for the same `market + trade_date + source=auto`, even after process restart.

- [ ] **Step 3: Keep startup backfill deterministic**

`src/main.py` should start the scheduler after the database is available, then trigger the `needs_backfill` / `backfill_recent_days` flow once per market if history is missing.

- [ ] **Step 4: Tag backfilled rows as seeded history**

`src/paper_ledger/backfill.py` should write provenance to the ledger rows so the dashboard can display the curve while still distinguishing seeded points from real daily runs.

**Acceptance Criteria:**

- `tests/test_daily_scheduler.py` still passes and proves the jobs exist for both markets.
- `tests/test_paper_ledger_backfill.py` proves the seeded history is created once and skipped on repeat runs.
- Restarting the app does not create duplicate auto runs for the same day.
- The dashboard can display a meaningful next-run time for each market.

---

## Phase 4: Frontend Data Binding And Interaction Flows

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**Objective:** Bind the new control-room shell to the new API suite. The page should load in stages, keep the dashboard responsive while data arrives, and make market and range switching feel like a single coherent system.

- [ ] **Step 1: Replace the one-shot render with a staged bootstrap flow**

Load in this order:

1. bootstrap summary
2. automation state
3. performance curve and comparison cards
4. run history and alerts

That makes the page usable even when one panel fails or is slow.

- [ ] **Step 2: Wire the market selector and range selector into data refetches**

The current market should control every request. The default read path should stay on `account_kind=auto`, while the manual sandbox stays isolated behind the run button.

- [ ] **Step 3: Render the NAV curve without adding a heavy chart dependency**

Use a lightweight canvas or SVG chart with:

- a thin line for NAV
- a subtle baseline grid
- hover or tap tooltips
- range pills for `7D / 30D / 90D / YTD`

Keep the chart visually secondary to the data cards. The point is clarity, not spectacle.

- [ ] **Step 4: Make the manual run flow explicit**

`POST /api/v1/dashboard/run` remains the manual sandbox trigger. Its result should land in the manual history lane and never overwrite the auto performance curve.

- [ ] **Step 5: Add loading, empty, and error states for each panel**

Each panel needs separate affordances for:

- loading
- empty history
- stale data
- failed request

**Acceptance Criteria:**

- Changing the market updates every dependent panel in one interaction cycle.
- The NAV chart is visible on first load and never renders as a blank box after data arrives.
- Manual run results are visually distinct from auto results.
- Alerts render when the watchlist is empty, the last auto run failed, or the dashboard data is stale.

---

## Phase 5: Verification, Docs, And Release Readiness

**Files:**
- Modify: `tests/test_dashboard_api.py`
- Modify: `tests/test_dashboard_performance.py`
- Modify: `tests/test_dashboard_page_contract.py`
- Modify: `tests/test_daily_scheduler.py`
- Modify: `tests/test_paper_ledger_store.py`
- Modify: `tests/test_paper_ledger_backfill.py`
- Modify: `docs/architecture.md`
- Modify: `docs/sop.md`

**Objective:** Pin the new contract, verify the new dashboard layout, and document the new automatic/manual split so future changes do not reintroduce ambiguity.

- [ ] **Step 1: Extend the API contract tests**

Pin the new payload shape, especially:

- `automation.today_status`
- `automation.last_run_at`
- `automation.next_run_at`
- `performance.nav_curve`
- `history.auto_runs`
- `history.manual_runs`
- `alerts`

- [ ] **Step 2: Add browser-level layout verification**

Verify the control-room shell at desktop, tablet, and mobile widths. Check for:

- no clipping
- no overlap
- readable axis labels
- stable status pills
- no stale labels from the old dashboard

- [ ] **Step 3: Update the user-facing docs**

`docs/sop.md` should explain:

- `auto` vs `manual` dashboard paths
- where the user sees daily automation status
- how the history curve should be interpreted

`docs/architecture.md` should explain:

- which data comes from `paper_ledger`
- which data still comes from the existing runtime store
- how the dashboard payload is composed

- [ ] **Step 4: Run the focused verification set**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_dashboard_api.py \
  tests/test_dashboard_performance.py \
  tests/test_dashboard_page_contract.py \
  tests/test_daily_scheduler.py \
  tests/test_paper_ledger_store.py \
  tests/test_paper_ledger_backfill.py -v
```

**Acceptance Criteria:**

- The targeted pytest set passes.
- The dashboard loads locally with the new layout and data-driven panels.
- The docs match the shipped interface names and data flow.
- No legacy dashboard language remains in the user-facing copy.

---

## Assumptions

- A single FastAPI instance owns the scheduler in the first release.
- `manual` sandbox runs stay available and never affect the `auto` performance curve.
- Backfill is seeded history, not real trading PnL, and should be labeled that way in the data model or UI.
- `market` is the primary filter axis; `account_kind` defaults to `auto` for dashboard reads.
- The dashboard should remain dense and operational, not decorative.
