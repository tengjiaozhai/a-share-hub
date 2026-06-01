# Dashboard Frontend Modularization Design

## Problem

`src/api/dashboard.html` is 2034 lines containing all HTML, CSS, and JavaScript in a single file. This makes it difficult to understand, modify, and maintain.

## Goal

Split the monolithic dashboard into modular JavaScript files while keeping the pure HTML/CSS/JS stack (no framework, no extra dev server). FastAPI serves all static files directly.

## Architecture

### Directory Structure

```
src/api/static/
├── index.html                 # SPA entry (nav + view containers)
├── css/
│   └── dashboard.css          # All styles (extracted from <style>)
└── js/
    ├── app.js                 # Route management + view switching + init
    ├── utils.js               # Pure utility functions (escapeHtml, formatDate, etc.)
    ├── api.js                 # API fetch wrapper + error handling
    ├── state.js               # Global mutable state (pagination, execMode, killSwitch)
    └── views/
        ├── dashboard.js       # Workbench view (decisions, orders, targets, config)
        ├── market.js          # Market view (search, quotes, watchlist)
        └── alpha.js           # Alpha view (assets, tickets, portfolio, reconciliation)
```

### File Responsibilities

| File | Est. Lines | Responsibility |
|------|------------|----------------|
| `index.html` | ~100 | HTML skeleton, nav bar, view container placeholders |
| `dashboard.css` | ~400 | All CSS styles |
| `app.js` | ~80 | Hash route listener, view switching, init entry |
| `utils.js` | ~100 | Pure functions: formatting, HTML escaping |
| `api.js` | ~80 | fetch wrapper, error handling, API endpoint constants |
| `state.js` | ~50 | Global state: pagination, exec mode, kill switch |
| `dashboard.js` | ~300 | Workbench view rendering and interaction |
| `market.js` | ~300 | Market view rendering and interaction |
| `alpha.js` | ~200 | Alpha view rendering and interaction |

## Routing

URL hash routing: `#/dashboard`, `#/market`, `#/alpha`

```javascript
// app.js
const routes = {
  '#/dashboard': { init: initDashboard, render: renderDashboard },
  '#/market':    { init: initMarket,    render: renderMarket },
  '#/alpha':     { init: initAlpha,     render: renderAlpha },
};

function navigateTo(hash) {
  const route = routes[hash] || routes['#/dashboard'];
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(hash.replace('#/', 'view-')).classList.add('active');
  route.render();
  window.location.hash = hash;
}

window.addEventListener('hashchange', () => navigateTo(window.location.hash));
```

Each view module exports two functions:

```javascript
// views/alpha.js
function initAlpha() {}   // Called once on first load (bind events, load initial data)
function renderAlpha() {} // Called every time view is switched (refresh data, update UI)
```

## API Layer

```javascript
// api.js
const API_BASE = '/api/v1';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}

const AlphaAPI = {
  getAssets:       ()         => apiFetch('/alpha/assets'),
  getTickets:      ()         => apiFetch('/alpha/tickets'),
  createTicket:    (data)     => apiFetch('/alpha/tickets', { method: 'POST', body: JSON.stringify(data) }),
  approveTicket:   (id)       => apiFetch(`/alpha/tickets/${id}/approve`, { method: 'POST' }),
  createFill:      (id, data) => apiFetch(`/alpha/tickets/${id}/fills`, { method: 'POST', body: JSON.stringify(data) }),
  getCapabilities: ()         => apiFetch('/alpha/capabilities'),
  getWorkbench:    ()         => apiFetch('/dashboard/workbench'),
};
```

Data flow: User action → view.js calls API → API returns data → view.js updates DOM

## Error Handling

- `apiFetch` catches errors and calls `showToast(message, 'error')`
- Button loading state via `setButtonLoading(btn, loading, originalText)`
- Toast notifications preserved from existing code

## FastAPI Static File Serving

```python
# src/api/routes_dashboard.py
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")
```

## Migration Strategy

### Phase 1: Extract Public Modules

- Create `src/api/static/` directory structure
- Extract CSS → `static/css/dashboard.css`
- Extract `utils.js` (pure functions, no dependencies)
- Extract `api.js` (API wrapper)

### Phase 2: Split Views

- Extract `dashboard.js` (workbench logic)
- Extract `market.js` (market logic)
- Extract `alpha.js` (Alpha logic)
- Create `app.js` (route management)

### Phase 3: Refactor index.html

- Slim down to HTML skeleton (~100 lines)
- Load JS via `<script type="module">`
- FastAPI mounts static directory

### Phase 4: Verify

- All page functions work correctly
- Route switching has no flicker
- API calls work normally

## Compatibility

- Keep original `src/api/dashboard.html` as backup
- Old and new paths coexist temporarily:
  - `/dashboard` (old, full HTML)
  - `/static/index.html` (new, modular)

## Testing

- Manual testing of all three views (dashboard, market, alpha)
- Verify route switching works
- Verify API calls succeed
- Verify error handling shows toast notifications
