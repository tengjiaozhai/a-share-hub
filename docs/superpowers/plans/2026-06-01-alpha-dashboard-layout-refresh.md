# Alpha Dashboard Layout Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持现有深色工作台风格与 Alpha 行为契约不变的前提下，将 Alpha 页面从纵向堆叠卡片重构为“状态总览 + 录单操作 + 数据区”三段式指挥台布局。

**Architecture:** 只改 `view_alpha.html` 的结构、`dashboard.css` 的 Alpha 专属样式、`alpha.js` 的最小渲染标记，所有 API 调用、表单提交 payload、DOM 主 id 均保持不变。通过先加失败测试锁定布局契约，再做最小实现，逐段收敛布局结构、响应式规则和动态列表渲染。最终验收以 `/dashboard` 响应内容和现有测试为权威，不引入新入口或新依赖。

**Tech Stack:** FastAPI dashboard renderer, vanilla HTML/CSS/JS, pytest, TestClient

---

## Scope Check

- 本次仅覆盖 Alpha 视图版式刷新（单一子系统），不拆分多计划。
- 非目标：
  - 不新增路由、不改 API、不中断 `submitAlphaTicket/runAlphaScan/proposeTopAlphaTicket`。
  - 不改全局主题变量，不引入新前端框架。
  - 不做 Alpha 业务功能扩展。

## File Structure Lock

- Modify: `src/api/dashboard_page/partials/view_alpha.html`
  - 重排为 Hero + status grid + ops grid + data grid 三段结构。
- Modify: `src/api/dashboard_page/styles/dashboard.css`
  - 新增 Alpha 专属布局/卡片/响应式样式，保留现有主题色。
- Modify: `src/api/dashboard_page/scripts/alpha.js`
  - 将资产、建议单、观察列表、候选输出由裸文本改为 class 化结构。
- Modify: `tests/test_dashboard_page_contract.py`
  - 增加布局契约、样式契约、脚本标记契约测试。
- Modify: `tests/test_dashboard_alpha_tab.py`
  - 从“旧纵向卡片文本断言”升级为“新分区结构 + 关键功能钩子”断言。

## Acceptance Gates

1. `/dashboard` 中 `view-alpha` 必须包含：
   - `alpha-hero`
   - `alpha-status-grid`
   - `alpha-ops-grid`
   - `alpha-data-grid`
2. 现有核心 id 与 handler 不变：
   - `alpha-execution-mode`
   - `alpha-execution-reason`
   - `alpha-portfolio-summary`
   - `alpha-positions`
   - `alpha-exceptions`
   - `alpha-assets`
   - `alpha-ticket-form`
   - `alpha-tickets`
   - `alpha-watchlist`
   - `alpha-candidates`
   - `submitAlphaTicket`
   - `runAlphaScan`
   - `proposeTopAlphaTicket`
3. `dashboard.css` 存在 Alpha 专属布局与响应式规则，不影响其他 tab。
4. `alpha.js` 不再输出大段内联 style 字符串，改为 class 化标记。
5. 相关测试通过：
   - `tests/test_dashboard_page_contract.py`
   - `tests/test_dashboard_alpha_tab.py`

---

### Task 1: Lock The New Alpha Layout Contract In Tests

**Files:**
- Modify: `tests/test_dashboard_page_contract.py`
- Modify: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: Write failing tests for new Alpha section topology**

```python
# tests/test_dashboard_page_contract.py
def test_render_dashboard_html_contains_alpha_desk_sections():
    html = render_dashboard_html()
    required = [
        'class="view alpha-desk" id="view-alpha"',
        'class="alpha-hero"',
        'class="alpha-status-grid"',
        'class="alpha-ops-grid"',
        'class="alpha-data-grid"',
        'id="alpha-execution-capability"',
        'id="alpha-ticket-form"',
        'id="alpha-assets"',
        'id="alpha-watchlist"',
        'id="alpha-candidates"',
    ]
    for marker in required:
        assert marker in html
```

```python
# tests/test_dashboard_alpha_tab.py
def test_dashboard_alpha_tab_uses_desk_layout_sections():
    html = _dashboard_html()
    assert 'class="alpha-hero"' in html
    assert 'class="alpha-status-grid"' in html
    assert 'class="alpha-ops-grid"' in html
    assert 'class="alpha-data-grid"' in html
```

- [ ] **Step 2: Run tests to verify they fail on current markup**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_alpha_desk_sections tests/test_dashboard_alpha_tab.py::test_dashboard_alpha_tab_uses_desk_layout_sections -v`
Expected: FAIL，提示缺少 `alpha-hero`/`alpha-status-grid` 等新布局标记。

- [ ] **Step 3: Add minimal layout anchors in `view_alpha.html` without changing behavior**

```html
<div class="view alpha-desk" id="view-alpha">
  <section class="alpha-hero">
    <p class="alpha-kicker">Alpha Desk</p>
    <h2>Alpha 代币化证券</h2>
    <p class="alpha-summary">半自动执行台，先确认执行能力，再录入建议单，再回看资产与候选。</p>
  </section>
  <section class="alpha-status-grid">...</section>
  <section class="alpha-ops-grid">...</section>
  <section class="alpha-data-grid">...</section>
</div>
```

- [ ] **Step 4: Re-run the tests to verify pass**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_alpha_desk_sections tests/test_dashboard_alpha_tab.py::test_dashboard_alpha_tab_uses_desk_layout_sections -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py src/api/dashboard_page/partials/view_alpha.html
git commit -m "test: lock alpha desk layout section contract"
```

### Task 2: Implement Command-Center HTML Structure

**Files:**
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write failing tests for section-to-content binding**

```python
# tests/test_dashboard_page_contract.py
import re

def test_alpha_status_grid_contains_capability_portfolio_exceptions():
    html = render_dashboard_html()
    pattern = r'class="alpha-status-grid"[\s\S]*id="alpha-execution-capability"[\s\S]*id="alpha-portfolio-summary"[\s\S]*id="alpha-exceptions"'
    assert re.search(pattern, html)


def test_alpha_ops_grid_contains_form_and_ticket_queue():
    html = render_dashboard_html()
    pattern = r'class="alpha-ops-grid"[\s\S]*id="alpha-ticket-form"[\s\S]*id="alpha-tickets"'
    assert re.search(pattern, html)


def test_alpha_data_grid_contains_assets_and_research_blocks():
    html = render_dashboard_html()
    pattern = r'class="alpha-data-grid"[\s\S]*id="alpha-assets"[\s\S]*id="alpha-watchlist"[\s\S]*id="alpha-candidates"'
    assert re.search(pattern, html)
```

- [ ] **Step 2: Run tests to verify they fail before full restructuring**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_alpha_status_grid_contains_capability_portfolio_exceptions tests/test_dashboard_page_contract.py::test_alpha_ops_grid_contains_form_and_ticket_queue tests/test_dashboard_page_contract.py::test_alpha_data_grid_contains_assets_and_research_blocks -v`
Expected: FAIL，说明新分区尚未完整绑定目标内容。

- [ ] **Step 3: Rewrite `view_alpha.html` to the three-stage desk layout**

```html
<div class="view alpha-desk" id="view-alpha">
  <section class="alpha-hero">
    <div class="alpha-hero-copy">
      <p class="alpha-kicker">Alpha Desk</p>
      <h2>Alpha 代币化证券</h2>
      <p class="alpha-summary">半自动执行台，先确认执行能力，再录入建议单，再回看资产与候选。</p>
    </div>
  </section>

  <section class="alpha-status-grid">
    <article class="alpha-panel" id="alpha-execution-capability">
      <div class="alpha-panel-label">Direct Execution Capability</div>
      <div id="alpha-execution-mode"></div>
      <div id="alpha-execution-reason"></div>
    </article>
    <article class="alpha-panel">
      <div class="alpha-panel-label">Alpha 组合</div>
      <div id="alpha-portfolio-summary"></div>
      <div id="alpha-positions"></div>
    </article>
    <article class="alpha-panel">
      <div class="alpha-panel-label">Alpha 异常</div>
      <div id="alpha-exceptions"></div>
    </article>
  </section>

  <section class="alpha-ops-grid">
    <article class="alpha-panel alpha-panel-form">
      <div class="alpha-panel-label">建议单录入</div>
      <form id="alpha-ticket-form" onsubmit="submitAlphaTicket(event)">
        <div class="alpha-ticket-grid">
          <input id="alpha-symbol" placeholder="资产代码 (如 AAPL)" />
          <input id="alpha-underlying" placeholder="标的代码 (如 AAPL.US)" />
          <input id="alpha-qty" type="number" placeholder="数量" />
          <input id="alpha-limit" type="number" step="0.01" placeholder="限价" />
        </div>
        <textarea id="alpha-thesis" placeholder="投资逻辑"></textarea>
        <button type="submit">创建建议单</button>
      </form>
    </article>

    <article class="alpha-panel alpha-panel-queue">
      <div class="alpha-panel-label">建议单队列</div>
      <div id="alpha-tickets"></div>
    </article>
  </section>

  <section class="alpha-data-grid">
    <article class="alpha-panel">
      <div class="alpha-panel-label">资产状态</div>
      <div id="alpha-assets"></div>
    </article>
    <article class="alpha-panel">
      <div class="alpha-panel-label">观察列表与候选</div>
      <div class="alpha-actions">
        <button type="button" onclick="runAlphaScan()">运行扫描</button>
        <button type="button" onclick="proposeTopAlphaTicket()">生成建议单</button>
      </div>
      <div id="alpha-watchlist"></div>
      <div id="alpha-candidates"></div>
    </article>
  </section>
</div>
```

- [ ] **Step 4: Re-run tests to verify the structural contract passes**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_alpha_status_grid_contains_capability_portfolio_exceptions tests/test_dashboard_page_contract.py::test_alpha_ops_grid_contains_form_and_ticket_queue tests/test_dashboard_page_contract.py::test_alpha_data_grid_contains_assets_and_research_blocks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard_page/partials/view_alpha.html tests/test_dashboard_page_contract.py
git commit -m "refactor: reorganize alpha panel into command-center layout"
```

### Task 3: Add Alpha-Specific Grid And Responsive CSS

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write failing CSS contract tests for new layout selectors**

```python
# tests/test_dashboard_page_contract.py
from pathlib import Path

def test_alpha_desk_css_selectors_exist():
    css = Path("src/api/dashboard_page/styles/dashboard.css").read_text(encoding="utf-8")
    required_selectors = [
        ".alpha-desk",
        ".alpha-hero",
        ".alpha-status-grid",
        ".alpha-ops-grid",
        ".alpha-data-grid",
        ".alpha-panel",
        ".alpha-ticket-grid",
        ".alpha-actions",
    ]
    for selector in required_selectors:
        assert selector in css


def test_alpha_desk_css_has_responsive_breakpoints():
    css = Path("src/api/dashboard_page/styles/dashboard.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1100px)" in css
    assert "@media (max-width: 768px)" in css
```

- [ ] **Step 2: Run tests to verify failure before CSS is added**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_alpha_desk_css_selectors_exist tests/test_dashboard_page_contract.py::test_alpha_desk_css_has_responsive_breakpoints -v`
Expected: FAIL，旧 CSS 缺少新布局选择器与断点规则。

- [ ] **Step 3: Implement scoped Alpha desk styles in `dashboard.css`**

```css
#view-alpha.alpha-desk{
  padding:20px;
  display:flex;
  flex-direction:column;
  gap:14px;
  height:calc(100vh - 40px);
  overflow-y:auto;
}

#view-alpha .alpha-status-grid{
  display:grid;
  grid-template-columns:repeat(3, minmax(0, 1fr));
  gap:12px;
}

#view-alpha .alpha-ops-grid{
  display:grid;
  grid-template-columns:minmax(0, 2fr) minmax(0, 1.3fr);
  gap:12px;
}

#view-alpha .alpha-data-grid{
  display:grid;
  grid-template-columns:minmax(0, 1.2fr) minmax(0, 1fr);
  gap:12px;
}

@media (max-width: 1100px){
  #view-alpha .alpha-status-grid{grid-template-columns:repeat(2, minmax(0, 1fr));}
  #view-alpha .alpha-ops-grid,
  #view-alpha .alpha-data-grid{grid-template-columns:1fr;}
}

@media (max-width: 768px){
  #view-alpha.alpha-desk{padding:12px;gap:10px;}
  #view-alpha .alpha-status-grid{grid-template-columns:1fr;}
}
```

- [ ] **Step 4: Re-run CSS contract tests**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_alpha_desk_css_selectors_exist tests/test_dashboard_page_contract.py::test_alpha_desk_css_has_responsive_breakpoints -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard_page/styles/dashboard.css tests/test_dashboard_page_contract.py
git commit -m "style: add alpha desk grid and responsive layout rules"
```

### Task 4: Minimal `alpha.js` Markup Upgrade For Dynamic Rows

**Files:**
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write failing script contract tests for class-based dynamic markup**

```python
# tests/test_dashboard_page_contract.py
def test_alpha_script_uses_class_based_row_markup():
    from pathlib import Path

    script = Path("src/api/dashboard_page/scripts/alpha.js").read_text(encoding="utf-8")
    required_markers = [
        "alpha-ticket-item",
        "alpha-asset-row",
        "alpha-watch-item",
        "alpha-candidate-item",
    ]
    for marker in required_markers:
        assert marker in script

    assert "style=\"display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px\"" not in script
```

- [ ] **Step 2: Run test to verify failure against current script**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_alpha_script_uses_class_based_row_markup -v`
Expected: FAIL，当前 `alpha.js` 仍包含内联 style 模板。

- [ ] **Step 3: Refactor render functions to emit semantic row classes**

```javascript
function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty">暂无建议单</div>';
    return;
  }
  root.innerHTML = items.map((item) => `
    <div class="alpha-ticket-item">
      <div class="alpha-ticket-main">
        <strong>${escapeHtml(item.asset_symbol)}</strong>
        <span>${escapeHtml(item.action)}</span>
      </div>
      <div class="alpha-ticket-meta">
        <span>${escapeHtml(String(item.suggested_quantity))}</span>
        <span>@ ${escapeHtml(String(item.suggested_limit_price))}</span>
        <span>${escapeHtml(item.status)}</span>
      </div>
    </div>
  `).join('');
}

function renderAlphaWatchlist(items) {
  const root = document.getElementById('alpha-watchlist');
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty">暂无观察标的</div>';
    return;
  }
  root.innerHTML = items.map(item => `
    <div class="alpha-watch-item">
      <span>${escapeHtml(item.symbol)}</span>
      <span>${escapeHtml(item.underlying_symbol)}</span>
      <span>优先级: ${item.priority}</span>
    </div>
  `).join('');
}
```

- [ ] **Step 4: Run verification tests for Alpha page contracts**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard_page/scripts/alpha.js tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py
git commit -m "refactor: upgrade alpha dynamic row markup for desk layout"
```

## Final Verification Gate

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py tests/test_dashboard_market_tab.py -v`
Expected: PASS（允许存在 warning，不允许 FAIL/ERROR）。

Run: `rg -n "id=\"alpha-execution-mode\"|id=\"alpha-ticket-form\"|runAlphaScan|proposeTopAlphaTicket|submitAlphaTicket" src/api/dashboard_page 2>&1 | head -c 4000`
Expected: 所有关键 id 和 handler 仍存在。

Run: `/opt/anaconda3/envs/py311/bin/python3 -m uvicorn src.main:build_app --factory --host 127.0.0.1 --port 8000`
Expected: 打开 `http://127.0.0.1:8000/dashboard#/alpha` 后，首屏可见 Hero + 状态三卡 + 录单/队列双栏 + 资产/候选双栏，移动端宽度下能自动堆叠。

## Self-Review

### 1. Spec Coverage

- 布局三段式：Task 2
- 深色工作台风格且仅改排版：Task 3
- 保留 id/handler 与行为契约：Task 1 + Task 4
- 动态内容不再“调试文本感”：Task 4
- 响应式要求：Task 3

无遗漏项。

### 2. Placeholder Scan

- 本计划未使用 `TBD`/`TODO`/“后续补充”。
- 每个任务都有可执行命令和明确 Expected。

### 3. Type Consistency

- `alpha-*` id 命名在测试、HTML、JS 三处保持一致。
- handler 名称 `submitAlphaTicket/runAlphaScan/proposeTopAlphaTicket` 在任务中一致。
