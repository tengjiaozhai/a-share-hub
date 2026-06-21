# Alpha Holdings Manual Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make holdings analysis save real buy records with manual cost, aggregate multiple buys into current holdings with weighted average cost, and show close-of-day profit/loss in the dashboard.

**Architecture:** Replace the draft-only `analysis_positions` preference path with a single authoritative holdings-entry path. Persist each buy record, rebuild aggregated positions and portfolio snapshot from those records using the latest completed close, then have both the workbench panel and the report read from that same source of truth.

**Tech Stack:** FastAPI, SQLAlchemy runtime store, vanilla JS dashboard, pytest, Alembic

---

### Task 1: Backend holdings-entry data path

**Files:**
- Create: `alembic/versions/20260621_000018_add_alpha_holdings_entries.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_runtime_store.py`

- [ ] Add a new `alpha_holdings_entries` table keyed by `entry_id`, storing `user_id`, `symbol`, `buy_date`, `buy_price`, `quantity`, timestamps.
- [ ] Write runtime-store tests first for create/list/update/delete and tenant isolation.
- [ ] Verify the new tests fail.
- [ ] Implement the store methods with no fallback to `analysis_positions`.
- [ ] Re-run `tests/test_alpha_runtime_store.py` and keep it green.

### Task 2: Backend aggregation and API

**Files:**
- Modify: `src/alpha/portfolio_service.py`
- Modify: `src/alpha/report_service.py`
- Modify: `src/api/routes_alpha.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_portfolio_service.py`
- Test: `tests/test_alpha_portfolio_report_service.py`
- Test: `tests/test_alpha_routes.py`

- [ ] Write failing tests for: weighted average cost from multiple buys, latest completed close PnL, edit/delete reflow, report reading saved holdings, and route contracts for list/create/update/delete.
- [ ] Verify those tests fail for the expected reason.
- [ ] Implement a single rebuild path from holdings entries to `alpha_positions` and portfolio snapshot.
- [ ] Add holdings CRUD endpoints under `/api/v1/alpha/holdings`.
- [ ] Make `/api/v1/alpha/portfolio/report` read saved holdings when no draft positions are passed, and return saved-position analysis with actual aggregated quantity/cost/mark.
- [ ] Re-run the alpha backend tests and keep them green.

### Task 3: Dashboard frontend save-and-refresh flow

**Files:**
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Test: `tests/test_dashboard_alpha_tab.py`
- Test: `tests/test_dashboard_page_contract.py`

- [ ] Write failing contract tests for the new holdings endpoints and the updated builder/history hooks.
- [ ] Verify those tests fail.
- [ ] Replace preference-based save/load with holdings API calls.
- [ ] On save, append the entered buy records, clear the draft builder or refresh it from saved records, refresh current holdings, and auto-run analysis.
- [ ] Add saved-record history with edit/delete controls.
- [ ] Keep the existing visual language; change only the controls and data hooks required for the feature.
- [ ] Re-run the dashboard contract tests and keep them green.

### Task 4: Integration verification

**Files:**
- Modify only if verification exposes a real issue.

- [ ] Run the directly affected pytest targets together.
- [ ] Start the local service.
- [ ] Log into the dashboard with the provided account in Chrome and validate, from a PM point of view, that save -> current holdings -> weighted cost -> close PnL -> edit/delete all work end to end.
