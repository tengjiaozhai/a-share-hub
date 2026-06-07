# Dashboard Theme Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global theme switcher to `dashboard_page` with 8 named themes, server-persisted preference, and first-paint consistency across all dashboard views.

**Architecture:** Theme is a first-class dashboard preference. The browser owns the theme registry and runtime toggle behavior, while FastAPI stores only `theme_id` and injects the current theme into the initial HTML so the page never flashes the wrong palette. All dashboard UI must consume semantic CSS variables instead of hard-coded colors; theme variants are defined as token sets inspired by the Open Design systems reference.

**Tech Stack:** FastAPI, Jinja-rendered HTML, vanilla CSS/JS, CSS custom properties, `pytest`, browser QA

---

## File Structure

| File | Responsibility |
|---|---|
| `src/api/dashboard_page/shell.html` | Add a root `data-theme` hook and load order for the theme bootstrap script |
| `src/api/dashboard_page/partials/status_bar.html` | Add the global right-top theme switch trigger and dropdown container |
| `src/api/dashboard_page/styles/dashboard.css` | Define theme tokens, per-theme overrides, and component token consumption |
| `src/api/dashboard_page/scripts/theme.js` | Theme registry, apply/save helpers, menu rendering, keyboard and click behavior |
| `src/api/dashboard_page/scripts/dashboard.js` | Read current theme from preferences and keep existing dashboard saves in sync |
| `src/api/dashboard_page/scripts/bootstrap.js` | Initialize theme state before the dashboard panels start polling or rendering |
| `src/api/dashboard_page/render.py` | Inject the saved theme into the initial HTML and include `theme.js` in the script order |
| `src/api/routes_dashboard.py` | Persist and validate `theme_id` in dashboard preferences |
| `tests/test_dashboard_api.py` | Verify preferences round-trip and invalid `theme_id` rejection |
| `tests/test_dashboard_page_contract.py` | Verify the rendered dashboard contains the theme control and bootstrap contract |
| `tests/test_dashboard_theme.py` | Verify theme switch behavior, initial theme injection, and persistence on refresh |

---

## Phase 1: Theme Token System

**Goal:** Establish a token-driven theme registry that can express 8 named themes without changing component code each time the palette changes.

**Files:**
- Create: `src/api/dashboard_page/scripts/theme.js`
- Modify: `src/api/dashboard_page/styles/dashboard.css`

- [ ] **Step 1: Define the theme registry and canonical theme IDs**

```javascript
const THEME_IDS = [
  'trading-terminal',
  'mission-control',
  'neutral-modern',
  'hud-signal',
  'mono-grid',
  'openai-editorial',
  'nvidia-power',
  'coinbase-institutional',
];

const THEMES = {
  'trading-terminal': { label: 'Trading Terminal', intent: 'dark control room' },
  'mission-control': { label: 'Mission Control', intent: 'navy and amber telemetry' },
  'neutral-modern': { label: 'Neutral Modern', intent: 'balanced light reading' },
  'hud-signal': { label: 'HUD Signal', intent: 'high-contrast operational dark' },
  'mono-grid': { label: 'Mono Grid', intent: 'terminal-like monochrome' },
  'openai-editorial': { label: 'OpenAI Editorial', intent: 'calm dark editorial' },
  'nvidia-power': { label: 'NVIDIA Power', intent: 'performance green on black' },
  'coinbase-institutional': { label: 'Coinbase Institutional', intent: 'clean finance white' },
};
```

- [ ] **Step 2: Replace raw dashboard colors with semantic CSS variables**

```css
:root {
  --bg: #0b1117;
  --panel: #101922;
  --panel-2: #0e1520;
  --text: #e7edf5;
  --muted: #94a3b8;
  --accent: #4dd4c6;
  --accent-2: #8ab4ff;
  --positive: #22c55e;
  --negative: #ef4444;
  --warning: #eab308;
  --border: rgba(255, 255, 255, 0.08);
}

html[data-theme='mission-control'] { /* token overrides */ }
html[data-theme='neutral-modern'] { /* token overrides */ }
```

Use semantic tokens only for cards, badges, tables, charts, buttons, alerts, and status rails. Keep theme overrides in one place and avoid component-level palette branches.

- [ ] **Step 3: Keep the theme menu itself token-based**

The switcher popup, selected state, hover state, and palette swatches must inherit from the active theme so the control remains readable in all 8 variants.

**Acceptance Criteria:**

- The registry contains exactly the 8 approved theme IDs and one default.
- Theme styles are driven through CSS variables and `html[data-theme="..."]` overrides, not component-local hard-coded colors.
- The default `trading-terminal` theme is legible on the current dashboard shell before any interaction.
- The theme switcher UI remains readable in both dark and light variants.

---

## Phase 2: Global Switcher Shell

**Goal:** Add a right-top global theme switcher that is visible from every dashboard view and does not interfere with `KILL SWITCH` or the existing nav group.

**Files:**
- Modify: `src/api/dashboard_page/partials/status_bar.html`
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `src/api/dashboard_page/scripts/theme.js`

- [ ] **Step 1: Add the trigger and dropdown markup into the global status bar**

```html
<div class="theme-switcher" id="theme-switcher">
  <button id="theme-switcher-btn" aria-haspopup="menu" aria-expanded="false">
    <i class="bi bi-palette"></i>
    <span id="theme-switcher-label">Trading Terminal</span>
  </button>
  <div class="theme-menu" id="theme-menu" role="menu" hidden></div>
</div>
```

Place the switcher on the far right, immediately before or alongside `KILL SWITCH`, so it reads as a global control rather than a page-local widget.

- [ ] **Step 2: Implement open/close, selection, and keyboard behavior**

```javascript
function applyTheme(themeId) { /* set data-theme and update button label */ }
function openThemeMenu() { /* show menu and focus selected item */ }
function closeThemeMenu() { /* hide menu and restore button state */ }
function bindThemeMenu() { /* click, outside-click, Esc, arrow key handling */ }
```

The menu should close on outside click and `Escape`, support keyboard navigation, and keep the current theme visibly selected.

- [ ] **Step 3: Keep the switcher from breaking the existing global nav**

The right-top area currently contains the page nav, mode pill, service dots, dates, and `KILL SWITCH`. The new theme control must fit without forcing horizontal scroll or changing the current click targets.

**Acceptance Criteria:**

- The theme switcher is visible in the global right-top area on all four dashboard views.
- The menu opens and closes without shifting the status bar layout.
- The active theme is visibly indicated in the menu and in the switcher label.
- At `390px` width, the status bar still fits and the switcher remains usable.

---

## Phase 3: Preference Persistence And First Paint

**Goal:** Persist `theme_id` through existing dashboard preferences and make the initial HTML render with the saved theme so the user never sees a palette flash.

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/dashboard_page/render.py`
- Modify: `src/api/dashboard_page/shell.html`
- Modify: `src/api/dashboard_page/scripts/bootstrap.js`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

- [ ] **Step 1: Add `theme_id` to the dashboard preference contract**

```python
allowed_keys = {
    "watchlist",
    "market",
    "capital_base",
    "max_position_ratio",
    "stop_loss_ratio",
    "max_daily_loss_ratio",
    "execution_mode",
    "theme_id",
}

if filtered.get("theme_id") not in THEME_IDS:
    raise HTTPException(status_code=400, detail="invalid theme_id")
```

The server remains the source of truth. `GET /api/v1/dashboard/preferences` should return the saved `theme_id`, defaulting to `trading-terminal` when the preference has never been written.

- [ ] **Step 2: Inject the saved theme into the initial HTML**

```html
<html lang="zh-CN" data-theme="trading-terminal">
```

`render_dashboard_html()` should receive the resolved theme and output it into the root element before any panel scripts execute. This avoids a brief render in the wrong palette.

- [ ] **Step 3: Load the theme bootstrap before dashboard panel initialization**

`theme.js` must run before `dashboard.js`, `market.js`, `alpha.js`, and `bootstrap.js` finish wiring the page so the CSS variables are already in place when components render.

- [ ] **Step 4: Keep existing preference updates in sync**

When a user changes the theme, the front end should save only `theme_id` plus the existing dashboard preferences payload, without breaking the current `watchlist`, `market`, or sizing fields.

**Acceptance Criteria:**

- Refreshing the page preserves the selected theme.
- A browser restart preserves the selected theme.
- Invalid `theme_id` values are rejected server-side and do not become persisted state.
- Existing dashboard preferences continue to save and load without regression.

---

## Phase 4: Component Audit And Verification

**Goal:** Make every dashboard surface theme-safe and verify the switcher across desktop and mobile layouts.

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `src/api/dashboard_page/partials/view_market.html`
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `src/api/dashboard_page/partials/view_us_stock.html`
- Modify: `tests/test_dashboard_api.py`
- Modify: `tests/test_dashboard_page_contract.py`
- Create: `tests/test_dashboard_theme.py`

- [ ] **Step 1: Audit all dashboard surfaces for hard-coded palette values**

Replace any remaining direct color literals in cards, tables, chips, buttons, alerts, charts, and tab bars with semantic tokens that derive from the current theme.

- [ ] **Step 2: Add contract tests for the new theme preference path**

```python
def test_dashboard_preferences_round_trip_theme_id(client, store):
    response = client.put("/api/v1/dashboard/preferences", json={"theme_id": "mission-control"})
    assert response.status_code == 200
    assert client.get("/api/v1/dashboard/preferences").json()["theme_id"] == "mission-control"

def test_invalid_theme_id_is_rejected(client):
    response = client.put("/api/v1/dashboard/preferences", json={"theme_id": "not-a-theme"})
    assert response.status_code == 400
```

- [ ] **Step 3: Add rendered-HTML contract checks**

```python
def test_dashboard_html_includes_theme_bootstrap():
    html = render_dashboard_html(theme_id="trading-terminal")
    assert 'data-theme="trading-terminal"' in html
    assert "theme-switcher" in html
    assert "theme.js" in html
```

- [ ] **Step 4: Verify the theme switcher in the browser at multiple widths**

Check the dashboard at `1440px`, `1024px`, and `390px`:

- the theme switcher is visible and clickable
- the menu does not hide the `KILL SWITCH`
- text remains readable in every theme
- the nav bar and page content do not overlap

**Acceptance Criteria:**

- `pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py tests/test_dashboard_theme.py -v` passes.
- The dashboard renders correctly at desktop and mobile widths with the theme switcher enabled.
- No dashboard view contains unreadable text or invalid contrast in the 8 approved themes.
- The theme switcher does not interfere with existing dashboard actions, especially `KILL SWITCH` and the nav tabs.

---

## Assumptions

- The first release uses `trading-terminal` as the default theme.
- Theme preference storage is server-side only; no separate `localStorage` state is introduced.
- The 8 theme IDs above are the complete first-release set.
- The theme system applies to the shared `dashboard_page` shell and all dashboard subviews, not to market data APIs or backend strategy logic.
