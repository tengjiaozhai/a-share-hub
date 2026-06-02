# Dashboard Single-Path Re-Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 `/dashboard` 从单个超大 HTML 文件拆成可维护的多源文件，但浏览器入口仍然只有 `/dashboard`，并且保留完整工作台功能、RuntimeStore 持久化配置与历史数据可见性；同时彻底移除 `src/api/static/`、`StaticFiles` 挂载和 `/new`。

**Architecture:** 以当前 `GET /dashboard` 响应和 `GET /api/v1/dashboard/workbench` / `GET|PUT /api/v1/dashboard/preferences` 为唯一真相，不再维护 `/static/index.html` 这一套第二前端。新实现只做“源码级拆分”：服务端通过 `src/api/dashboard_page/render.py` 将 HTML partial、单份 CSS、按领域拆分的 JS 组装成一份完整页面返回给 `/dashboard`。这样前端不会再有第二套状态管理或第二条数据流，数据库数据继续只经由现有 API 读写。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy RuntimeStore, vanilla HTML/CSS/JS, pytest, TestClient, rg

---

## 范围与门控

- 本计划只解决 dashboard 拆分方式错误的问题：双入口、双前端实现、以及由此带来的功能阉割和持久化数据脱钩。
- 非目标：
  - 不新增 React/Vite/Jinja2/构建步骤。
  - 不顺手恢复当前仓库里并不存在的 crypto 视图。
  - 不修改 `routes_dashboard.py` 的 workbench / preferences / alpha / market JSON 契约。
- 真实执行路径已经确认：
  - `src/api/routes_dashboard.py:108-112` 的 `/dashboard` 直接读取 `src/api/dashboard.html`。
  - `src/main.py:8,105-108` 挂载了 `StaticFiles`。
  - `src/api/routes_dashboard.py:811-814` 暴露 `/new -> /static/index.html`。
- 当前测试状态已经确认：
  - `tests/test_dashboard_alpha_tab.py` 和 `tests/test_dashboard_market_tab.py` 直接读取 `src/api/dashboard.html`，这会阻止删除单体文件。
  - `tests/test_crypto_proxy.py` 里关于 crypto 视图的断言与当前 `/dashboard` 真实内容不一致，属于已有漂移；不要把它当作本次拆分验收标准。
- 脏工作树提示：
  - 当前 `src/api/static/index.html`、`src/api/static/js/api.js`、`src/api/static/js/utils.js`、`src/api/static/js/views/alpha.js`、`src/api/static/js/views/dashboard.js` 已有未提交修改。
  - 新拆分实现不要建立在这些文件之上；只允许在“先写失败测试，再证明 `/dashboard` 缺功能”后，按需从这些文件拷贝少量逻辑。

## 验收标准

1. `GET /dashboard` 返回 `200`，仍然包含当前工作台、实时行情、Alpha 三个视图以及运行/回测/扫描/Kill Switch 控件。
2. `/dashboard` 是唯一 HTML 入口：
   - `GET /dashboard` 为 `200`
   - `GET /new` 为 `404`
   - `GET /static/index.html` 为 `404`
3. 运行时代码中不再存在第二条前端入口：
   - `src/main.py` 不再导入或挂载 `StaticFiles`
   - `src/api/routes_dashboard.py` 不再引用 `dashboard.html` 文件路径
   - `src/api/routes_dashboard.py` 不再定义 `/new`
4. 自动化契约测试不再直接读取 `src/api/dashboard.html` 文件，而是通过 `TestClient` 断言 `/dashboard` 响应内容。
5. 基于临时 SQLite RuntimeStore 的集成测试证明：
   - `PUT /api/v1/dashboard/preferences` 保存的 watchlist / capital / risk 配置仍能被 `GET /api/v1/dashboard/preferences` 取回
   - 种入的 decision / target / order / broker event 仍能通过 `GET /api/v1/dashboard/workbench` 返回
   - `/dashboard` 页面源码仍然引用 `WORKBENCH_API` 与 `PREFS_API`，说明前端继续以服务端数据为权威源
6. `src/api/static/` 与 `src/api/dashboard.html` 在最终实现中都不存在。
7. 对活跃代码路径执行：
   - `rg -n "/static/index.html|src/api/static|StaticFiles|Path\\(\"src/api/dashboard.html\"\\)" src tests README.md docs/runbooks`
   - 预期：无匹配。

## 文件结构锁定

- Modify: `src/main.py:7-8, 99-108`
- Modify: `src/api/routes_dashboard.py:108-114, 791-814`
- Delete: `src/api/dashboard.html`
- Delete: `src/api/static/`
- Create: `src/api/dashboard_page/render.py`
- Create: `src/api/dashboard_page/shell.html`
- Create: `src/api/dashboard_page/partials/status_bar.html`
- Create: `src/api/dashboard_page/partials/view_dashboard.html`
- Create: `src/api/dashboard_page/partials/view_market.html`
- Create: `src/api/dashboard_page/partials/view_alpha.html`
- Create: `src/api/dashboard_page/styles/dashboard.css`
- Create: `src/api/dashboard_page/scripts/utils.js`
- Create: `src/api/dashboard_page/scripts/dashboard.js`
- Create: `src/api/dashboard_page/scripts/market.js`
- Create: `src/api/dashboard_page/scripts/alpha.js`
- Create: `src/api/dashboard_page/scripts/bootstrap.js`
- Create: `tests/test_dashboard_page_contract.py`
- Modify: `tests/test_dashboard_alpha_tab.py:1-36`
- Modify: `tests/test_dashboard_market_tab.py:1-8`
- Modify: `README.md` if it references `src/api/dashboard.html` or `/new`
- Modify: `docs/runbooks/dashboard_user_guide.md` if it references `src/api/dashboard.html` or `/new`
- Modify: `docs/superpowers/specs/2026-06-01-dashboard-frontend-modularization-design.md`

## 假设

- 新拆分仍然使用原生 HTML/CSS/JS，不引入模板引擎依赖。
- 页面最终交付给浏览器的仍然是一份完整 HTML；拆分只发生在仓库源码层，不额外暴露第二份前端资源目录。
- 本次验收以当前 `/dashboard` 实际功能为准，不以过时的 crypto 测试或旧 spec 为准。

### Task 1: 先收敛成单入口，切断 `/static` 运行路径

**Files:**
- Create: `tests/test_dashboard_page_contract.py`
- Modify: `src/main.py:7-8, 99-108`
- Modify: `src/api/routes_dashboard.py:811-814`

- [ ] **Step 1: 写失败测试，锁定“只有 `/dashboard` 能作为页面入口”**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def build_dashboard_client():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: store
    return TestClient(app), store


def test_dashboard_is_only_html_entrypoint():
    client, _ = build_dashboard_client()

    assert client.get("/dashboard").status_code == 200
    assert client.get("/new").status_code == 404
    assert client.get("/static/index.html").status_code == 404
```

- [ ] **Step 2: 运行测试，确认当前实现失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_dashboard_is_only_html_entrypoint -q`
Expected: FAIL，`/new` 或 `/static/index.html` 仍然返回 `200`

- [ ] **Step 3: 做最小实现，移除 `StaticFiles` 挂载和 `/new` 路由**

```python
# src/main.py
from fastapi import FastAPI

...

def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(decision_runs_router)
    app.include_router(portfolio_targets_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(reconciliation_router)
    app.include_router(kill_switch_router)
    app.include_router(market_router)
    app.include_router(dashboard_router)
    app.include_router(crypto_router)
    app.include_router(alpha_router)
    return app
```

```python
# src/api/routes_dashboard.py
@router.put("/api/v1/dashboard/preferences")
def save_preferences(config: dict) -> dict:
    store = get_runtime_store()
    allowed_keys = {
        "watchlist",
        "capital_base",
        "max_position_ratio",
        "stop_loss_ratio",
        "max_daily_loss_ratio",
        "execution_mode",
    }
    filtered = {k: v for k, v in config.items() if k in allowed_keys}
    store.set_preference("dashboard", filtered)
    return {"status": "ok"}
```

- [ ] **Step 4: 重新运行测试，确认单入口约束已建立**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_dashboard_is_only_html_entrypoint -q`
Expected: PASS

- [ ] **Step 5: 提交本任务**

```bash
git add src/main.py src/api/routes_dashboard.py tests/test_dashboard_page_contract.py
git commit -m "refactor: remove dashboard static entrypoints"
```

### Task 2: 引入服务端组装器，替换对 `src/api/dashboard.html` 的直接依赖

**Files:**
- Create: `src/api/dashboard_page/render.py`
- Create: `src/api/dashboard_page/shell.html`
- Create: `src/api/dashboard_page/partials/status_bar.html`
- Create: `src/api/dashboard_page/partials/view_dashboard.html`
- Create: `src/api/dashboard_page/partials/view_market.html`
- Create: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `src/api/routes_dashboard.py:108-112`
- Modify: `tests/test_dashboard_alpha_tab.py:1-36`
- Modify: `tests/test_dashboard_market_tab.py:1-8`

- [ ] **Step 1: 写失败测试，要求 `/dashboard` 来自 split source 而不是磁盘单文件**

```python
from fastapi.testclient import TestClient

from src.api.dashboard_page.render import render_dashboard_html
from src.main import build_app


def test_render_dashboard_html_contains_alpha_contract():
    html = render_dashboard_html()
    assert "view-alpha" in html
    assert "alpha-execution-capability" in html
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in html
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in html
    assert "runAlphaScan" in html
    assert "proposeTopAlphaTicket" in html


def test_render_dashboard_html_contains_market_contract():
    html = render_dashboard_html()
    assert "view-market" in html
    assert "tb-market-full" in html
    assert "实时行情" in html
    assert "refreshMarketQuotes" in html


def test_dashboard_route_uses_rendered_split_html():
    client = TestClient(build_app())
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert response.text == render_dashboard_html()
```

- [ ] **Step 2: 运行测试，确认当前实现失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py -q`
Expected: FAIL，原因是 `src.api.dashboard_page.render` 尚不存在

- [ ] **Step 3: 新建组装器和页面骨架，并让 `/dashboard` 调用组装器**

```python
# src/api/dashboard_page/render.py
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def render_dashboard_html() -> str:
    html = _read("shell.html")
    replacements = {
        "{{INLINE_STYLES}}": _read("styles/dashboard.css"),
        "{{STATUS_BAR}}": _read("partials/status_bar.html"),
        "{{VIEW_DASHBOARD}}": _read("partials/view_dashboard.html"),
        "{{VIEW_MARKET}}": _read("partials/view_market.html"),
        "{{VIEW_ALPHA}}": _read("partials/view_alpha.html"),
        "{{INLINE_UTILS_JS}}": _read("scripts/utils.js"),
        "{{INLINE_DASHBOARD_JS}}": _read("scripts/dashboard.js"),
        "{{INLINE_MARKET_JS}}": _read("scripts/market.js"),
        "{{INLINE_ALPHA_JS}}": _read("scripts/alpha.js"),
        "{{INLINE_BOOTSTRAP_JS}}": _read("scripts/bootstrap.js"),
    }
    for marker, content in replacements.items():
        html = html.replace(marker, content)
    return html
```

```html
<!-- src/api/dashboard_page/shell.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A股模拟工作台</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
{{INLINE_STYLES}}
  </style>
</head>
<body>
{{STATUS_BAR}}
{{VIEW_DASHBOARD}}
{{VIEW_MARKET}}
{{VIEW_ALPHA}}
<script>
{{INLINE_UTILS_JS}}
</script>
<script>
{{INLINE_DASHBOARD_JS}}
</script>
<script>
{{INLINE_MARKET_JS}}
</script>
<script>
{{INLINE_ALPHA_JS}}
</script>
<script>
{{INLINE_BOOTSTRAP_JS}}
</script>
</body>
</html>
```

```python
# src/api/routes_dashboard.py
from src.api.dashboard_page.render import render_dashboard_html


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return render_dashboard_html()
```

- [ ] **Step 4: 重新运行测试，确认 `/dashboard` 已由 split source 生成**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py -q`
Expected: PASS

- [ ] **Step 5: 提交本任务**

```bash
git add src/api/routes_dashboard.py src/api/dashboard_page tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py
git commit -m "refactor: render dashboard from split source"
```

### Task 3: 拆出公共样式与工作台脚本，并锁定服务端持久化数据契约

**Files:**
- Create: `src/api/dashboard_page/styles/dashboard.css`
- Create: `src/api/dashboard_page/scripts/utils.js`
- Create: `src/api/dashboard_page/scripts/dashboard.js`
- Create: `src/api/dashboard_page/scripts/bootstrap.js`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: 写失败测试，锁定 `/dashboard` 继续依赖服务端 preferences/workbench**

```python
from datetime import datetime, timedelta


def test_dashboard_preferences_and_workbench_stay_server_backed():
    client, store = build_dashboard_client()

    store.set_preference(
        "dashboard",
        {
            "watchlist": ["600519.SH", "000858.SZ"],
            "capital_base": 1200000,
            "max_position_ratio": 0.25,
            "stop_loss_ratio": -0.05,
            "max_daily_loss_ratio": -0.03,
            "execution_mode": "full",
        },
    )

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="dashboard-seed",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.25,
        reason="seed decision",
        input_snapshot={"symbol": "600519.SH", "features": {"decision_mode": "mock"}, "market_context": {"mode": "shadow"}},
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=300000,
        target_position_ratio=0.25,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1000.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "paper-001"},
    )

    html = client.get("/dashboard").text
    prefs = client.get("/api/v1/dashboard/preferences").json()
    workbench = client.get("/api/v1/dashboard/workbench").json()

    assert "const WORKBENCH_API = '/api/v1/dashboard/workbench';" in html
    assert "const PREFS_API = '/api/v1/dashboard/preferences';" in html
    assert prefs["watchlist"] == ["600519.SH", "000858.SZ"]
    assert workbench["history"]["decisions"][0]["decision_run_id"] == decision_run_id
    assert workbench["history"]["targets"][0]["target_position_id"] == target_position_id
    assert workbench["history"]["orders"][0]["execution_order_id"] == execution_order_id
```

- [ ] **Step 2: 运行测试，确认当前 split source 还没有完整脚本资源**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_dashboard_preferences_and_workbench_stay_server_backed -q`
Expected: FAIL，通常表现为 `render_dashboard_html()` 读取不到 `styles/dashboard.css` 或 `scripts/*.js`

- [ ] **Step 3: 抽出 CSS / utils / dashboard / bootstrap，并保留原有 API 常量和配置保存逻辑**

```javascript
// src/api/dashboard_page/scripts/dashboard.js
const WORKBENCH_API = '/api/v1/dashboard/workbench';
const KILL_SWITCH_STATUS_API = '/api/v1/kill-switch/status';
const KILL_SWITCH_ACTIVATE_API = '/api/v1/kill-switch/activate';
const KILL_SWITCH_DEACTIVATE_API = '/api/v1/kill-switch/deactivate';
const PREFS_API = '/api/v1/dashboard/preferences';
const SCAN_API = '/api/v1/dashboard/scan';
const BACKTEST_API = '/api/v1/dashboard/backtest';

let execMode = 'full';
let killSwitchActive = false;
let simRunning = false;
let scanRunning = false;
let btRunning = false;
let dashboardTimersStarted = false;
let _savePrefsTimer = null;

function savePreferences() {
  clearTimeout(_savePrefsTimer);
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = '保存中...';
  statusEl.style.color = 'var(--yellow)';
  const prefs = {
    watchlist: document.getElementById('cfg-watchlist').value.split(',').map(s => s.trim()).filter(Boolean),
    capital_base: Number(document.getElementById('cfg-capital').value) * 10000,
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    execution_mode: execMode,
  };
  return fetch(PREFS_API, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  });
}
```

```javascript
// src/api/dashboard_page/scripts/bootstrap.js
document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
  loadDashboard();
});
```

- [ ] **Step 4: 重新运行测试，确认服务端持久化契约未断开**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py -q`
Expected: PASS

- [ ] **Step 5: 提交本任务**

```bash
git add src/api/dashboard_page/styles/dashboard.css src/api/dashboard_page/scripts/utils.js src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/scripts/bootstrap.js tests/test_dashboard_page_contract.py
git commit -m "refactor: extract dashboard workbench assets"
```

### Task 4: 拆出市场与 Alpha 视图脚本，并保持现有视图功能不减

**Files:**
- Create: `src/api/dashboard_page/scripts/market.js`
- Create: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/partials/view_market.html`
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `tests/test_dashboard_alpha_tab.py`
- Modify: `tests/test_dashboard_market_tab.py`

- [ ] **Step 1: 写失败测试，锁定 market/alpha 视图的关键 DOM 和 API 契约**

```python
def test_render_dashboard_html_contains_market_and_alpha_controls():
    html = render_dashboard_html()
    required_markers = [
        'id="tb-market-full"',
        'id="market-select"',
        'id="scan-btn"',
        'id="alpha-assets"',
        'id="alpha-ticket-form"',
        'id="alpha-execution-capability"',
        "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';",
        "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';",
        "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';",
        'runAlphaScan',
        'proposeTopAlphaTicket',
        'refreshMarketQuotes',
    ]
    for marker in required_markers:
        assert marker in html
```

- [ ] **Step 2: 运行测试，确认 market/alpha 拆分文件尚未补齐**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py -q`
Expected: FAIL，缺少 `market.js` 或 `alpha.js` 中的函数/常量

- [ ] **Step 3: 从当前单体页面逐段迁移 market/alpha 逻辑，不改行为只改归属**

```javascript
// src/api/dashboard_page/scripts/market.js
function refreshMarketQuotes() {
  const watchlistInput = document.getElementById('cfg-watchlist');
  if (!watchlistInput) return Promise.resolve();
  const symbols = watchlistInput.value
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 10);
  if (symbols.length === 0) {
    renderMarketQuotes([]);
    return Promise.resolve();
  }
  return fetch('/api/v1/market/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(symbols),
  })
    .then(res => res.json())
    .then(data => renderMarketQuotes(Array.isArray(data) ? data : []));
}
```

```javascript
// src/api/dashboard_page/scripts/alpha.js
const ALPHA_ASSETS_API = '/api/v1/alpha/assets';
const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';
const ALPHA_WATCHLIST_API = '/api/v1/alpha/watchlist';
const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';

async function loadAlphaAssets() {
  const res = await fetch(ALPHA_ASSETS_API);
  const data = await res.json();
  renderAlphaAssets(data.items || []);
}

async function submitAlphaTicket(event) {
  event.preventDefault();
  const payload = {
    asset_symbol: document.getElementById('alpha-symbol').value.trim(),
    underlying_symbol: document.getElementById('alpha-underlying').value.trim(),
    action: 'BUY',
    thesis: document.getElementById('alpha-thesis').value.trim(),
    suggested_quantity: Number(document.getElementById('alpha-qty').value),
    suggested_limit_price: Number(document.getElementById('alpha-limit').value),
    expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
  };
  await fetch(ALPHA_TICKETS_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 4: 重新运行测试，确认 market/alpha 视图契约仍然完整**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py tests/test_dashboard_page_contract.py -q`
Expected: PASS

- [ ] **Step 5: 提交本任务**

```bash
git add src/api/dashboard_page/scripts/market.js src/api/dashboard_page/scripts/alpha.js src/api/dashboard_page/partials/view_market.html src/api/dashboard_page/partials/view_alpha.html tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py
git commit -m "refactor: split dashboard market and alpha views"
```

### Task 5: 删除残留单体文件与 `static/` 目录，更新文档并完成最终验收

**Files:**
- Delete: `src/api/dashboard.html`
- Delete: `src/api/static/`
- Modify: `README.md`
- Modify: `docs/runbooks/dashboard_user_guide.md`
- Modify: `docs/superpowers/specs/2026-06-01-dashboard-frontend-modularization-design.md`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: 写失败测试，锁定“单体文件与 static 目录都必须消失”**

```python
from pathlib import Path


def test_dashboard_split_has_no_legacy_frontend_paths():
    assert not Path("src/api/dashboard.html").exists()
    assert not Path("src/api/static").exists()

    main_py = Path("src/main.py").read_text(encoding="utf-8")
    routes_py = Path("src/api/routes_dashboard.py").read_text(encoding="utf-8")

    assert "StaticFiles" not in main_py
    assert '/new' not in routes_py
    assert 'dashboard.html' not in routes_py
```

- [ ] **Step 2: 运行测试，确认遗留实现还没清理干净**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_dashboard_split_has_no_legacy_frontend_paths -q`
Expected: FAIL，`src/api/dashboard.html` 或 `src/api/static/` 仍然存在

- [ ] **Step 3: 删除遗留源码并更新活跃文档**

```markdown
<!-- docs/superpowers/specs/2026-06-01-dashboard-frontend-modularization-design.md -->
## Status

Superseded by `docs/superpowers/plans/2026-06-01-dashboard-single-path-resplit.md`.

- `src/api/static/` has been removed.
- `/dashboard` is the only browser entrypoint.
- Dashboard source now lives under `src/api/dashboard_page/` and is assembled server-side into one HTML response.
```

```markdown
<!-- README.md / docs/runbooks/dashboard_user_guide.md -->
- 打开工作台：`/dashboard`
- 不再使用：`/new`
- 不再使用：`src/api/static/`
```

- [ ] **Step 4: 跑最终自动化验证和 grep 验收**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py -q`
Expected: PASS

Run: `rg -n "/static/index.html|src/api/static|StaticFiles|Path\\(\"src/api/dashboard.html\"\\)" src tests README.md docs/runbooks 2>&1 | head -c 4000`
Expected: no output

Run: `/opt/anaconda3/envs/py311/bin/python3 -m uvicorn src.main:build_app --factory --host 127.0.0.1 --port 8000`
Expected: `GET http://127.0.0.1:8000/dashboard` 打开成功，且页面请求里不再出现 `/static/...`

- [ ] **Step 5: 提交本任务**

```bash
git add README.md docs/runbooks/dashboard_user_guide.md docs/superpowers/specs/2026-06-01-dashboard-frontend-modularization-design.md tests/test_dashboard_page_contract.py src/api/dashboard_page src/api/routes_dashboard.py src/main.py
git rm -r src/api/static src/api/dashboard.html
git commit -m "refactor: finish single-path dashboard split"
```

## 自检

- 覆盖性检查：
  - 双入口问题：Task 1, Task 5
  - 直接读 `dashboard.html`：Task 2, Task 5
  - 持久化配置/历史数据不能丢：Task 3
  - 市场/Alpha 功能不能阉割：Task 4
  - 文档与活跃路径要同步：Task 5
- Placeholder 检查：
  - 本计划没有使用 `TODO` / `TBD` / “自行处理” / “类似 Task N”。
  - 所有执行步骤都附了代码片段或命令。
- 类型与命名一致性：
  - 页面唯一入口统一使用 `/dashboard`
  - 组装函数统一命名为 `render_dashboard_html`
  - RuntimeStore 仍通过 `PREFS_API` / `WORKBENCH_API` 暴露，不引入第二状态源

## 备注

- 当前 `tests/test_crypto_proxy.py` 中对 crypto 视图和 `/api/v1/crypto/*` 的断言已经与仓库真实实现漂移。不要把那组失败当作本计划的验收阻塞项；如果要恢复 crypto 功能，应单开 plan。
- 如果在执行时发现 `src/api/static/*` 中某段逻辑确实比单体页更接近用户当前期望，先补一条失败的 `/dashboard` 契约测试，再把那段逻辑迁移到 `src/api/dashboard_page/`；不要直接把 `static/` 整包搬回来。
