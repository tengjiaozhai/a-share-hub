# Dashboard Drawer 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将案件视图从底部 rail 抽取为右侧滑出 drawer，解决 3 个 UX 问题：点击卡片无反应、运行记录占用过多空间、案件 Tab 不可达

**Architecture:** 复用现有 `.case-shell` 内部结构，抽取到 `position: fixed` 的 50% 宽度 drawer 容器。修改 `selectHistoryRun` 调用 `openCaseDrawer()` 触发滑出 + skeleton + snapshot 加载。运行记录改 2 列网格 + 64px 高度限制。

**Tech Stack:** Vanilla JS + CSS（无框架）、FastAPI 后端

**Reference:** 设计文档 `docs/superpowers/specs/2026-06-19-dashboard-drawer-design.md`

---

## File Structure

| 文件路径 | 职责 | 改动类型 |
|---------|------|---------|
| `src/api/dashboard_page/partials/view_dashboard.html` | 抽取 case-shell 到 drawer 容器 | Modify |
| `src/api/dashboard_page/styles/dashboard.css` | drawer 滑出 + 卡片紧凑化 + skeleton 样式 | Modify |
| `src/api/dashboard_page/scripts/dashboard.js` | openCaseDrawer/closeCaseDrawer + skeleton + ESC 键 | Modify |
| `tests/test_dashboard_page_contract.py` | 契约测试 | Modify |

---

## Task 1: HTML 抽取 — case-shell 从 rail-bottom 移到 drawer

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html:207-317`

**Success Criteria:**
- `view_dashboard.html` 中 `.rail-bottom` 容器被删除
- 新增 `<aside class="case-drawer" id="case-drawer">` 容器包含原 case-shell 内容
- 新增 `<div class="drawer-backdrop" id="drawer-backdrop">` 元素
- drawer 内包含 case-header、case-overview、case-stage-rail、case-stage-grid 全部原内容
- drawer 顶部有 `.case-drawer-head` 和 close 按钮

- [ ] **Step 1: 写失败的契约测试**

```python
# tests/test_dashboard_page_contract.py (追加)
def test_render_dashboard_html_contains_case_drawer_contract():
    """验证 drawer 容器和关闭控件已嵌入"""
    html = render_dashboard_html()
    assert 'id="case-drawer"' in html
    assert 'class="case-drawer"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'class="drawer-close"' in html
    assert 'openCaseDrawer' in html
    assert 'closeCaseDrawer' in html
    assert 'class="case-shell"' in html  # case-shell 仍然存在（在 drawer 内）
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_case_drawer_contract -v`
Expected: FAIL (drawer elements don't exist yet)

- [ ] **Step 3: 读取原 case-shell 完整内容**

Read: `src/api/dashboard_page/partials/view_dashboard.html:207-317`
确认需要保留的内部结构。

- [ ] **Step 4: 删除 rail-bottom 容器**

将 `src/api/dashboard_page/partials/view_dashboard.html:207-317` 整个 `<section class="rail-bottom">` 块替换为：

```html
</div>
</div>
```

（即在 `</aside>` 后直接结束 `dashboard-shell` 和 `view-dashboard` 容器）

- [ ] **Step 5: 在 view-dashboard 关闭标签前添加 drawer 容器**

在 `view_dashboard.html` 第 319 行（`</div>` 关闭 view-dashboard 之前）插入：

```html

<!-- ═══ CASE DRAWER (fixed overlay) ═══ -->
<aside class="case-drawer" id="case-drawer" aria-label="案件视图" aria-hidden="true">
  <div class="case-drawer-head">
    <span class="case-drawer-title">案件详情</span>
    <button type="button" class="drawer-close" id="drawer-close" onclick="closeCaseDrawer()" aria-label="关闭案件视图">×</button>
  </div>
  <div class="case-shell" id="case-shell">
    <div class="case-header">
      <div class="case-heading">
        <div class="section-kicker">案件视图</div>
        <h3 id="case-title">请选择运行记录</h3>
        <div class="case-subtitle" id="case-subtitle">从运行中心选择一条手动运行记录，查看完整链路。</div>
      </div>
      <div class="case-summary-chips" id="case-summary-chips"></div>
    </div>

    <div class="case-overview">
      <div class="case-overview-grid" id="case-overview-grid">
        <div class="overview-empty">
          <strong>概览等待加载</strong>
          <span>选中一条记录后，这里会同步展示决策、订单、目标仓位、对账和异常的摘要。</span>
        </div>
      </div>
      <div class="case-overview-note" id="case-overview-note">选择一条运行记录查看案件视图。</div>
    </div>

    <div class="case-stage-rail" id="case-stage-rail"></div>

    <div class="case-stage-grid">
      <div class="case-stage-pane active" id="case-pane-overview">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">链路时间线</div>
            <div class="case-stage-note">按阶段查看这轮运行的推进过程</div>
          </div>
        </div>
        <div class="timeline" id="case-timeline">
          <div class="timeline-empty" id="timeline-empty">
            选择一条运行记录查看链路时间线
          </div>
        </div>
      </div>

      <div class="case-stage-pane" id="case-pane-decisions">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">决策明细</div>
            <div class="case-stage-note">时间、动作、置信度和理由</div>
          </div>
          <div id="pag-decisions" class="pagination"></div>
        </div>
        <table><thead><tr><th>时间</th><th>股票</th><th>动作</th><th>置信度</th><th>理由</th></tr></thead><tbody id="tb-decisions"><tr><td colspan="5" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
      </div>

      <div class="case-stage-pane" id="case-pane-targets">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">目标仓位</div>
            <div class="case-stage-note">输出的目标数量、权重和理由</div>
          </div>
          <div id="pag-targets" class="pagination"></div>
        </div>
        <table><thead><tr><th>股票</th><th>目标数量</th><th>目标权重</th><th>理由</th></tr></thead><tbody id="tb-targets"><tr><td colspan="4" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
      </div>

      <div class="case-stage-pane" id="case-pane-orders">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">执行订单</div>
            <div class="case-stage-note">方向、数量、成交、手续费与盈亏</div>
          </div>
          <div id="pag-orders" class="pagination"></div>
        </div>
        <table><thead><tr><th>时间</th><th>股票</th><th>方向</th><th>数量</th><th>成交价</th><th>手续费</th><th>盈亏</th><th>状态</th></tr></thead><tbody id="tb-orders"><tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr></tbody></table>
      </div>

      <div class="case-stage-pane" id="case-pane-reconcile">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">对账结果</div>
            <div class="case-stage-note">持仓、价格、涨跌幅与未实现盈亏</div>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>股票</th>
              <th>数量</th>
              <th>成本价</th>
              <th>现价</th>
              <th>涨跌幅</th>
              <th>未实现盈亏</th>
              <th>手续费</th>
              <th>行情时间</th>
            </tr>
          </thead>
          <tbody id="tb-reconcile">
            <tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>
          </tbody>
        </table>
      </div>

      <div class="case-stage-pane" id="case-pane-errors">
        <div class="case-stage-pane-head">
          <div>
            <div class="case-stage-title">异常事件</div>
            <div class="case-stage-note">需要关注的错误、告警和阻断信息</div>
          </div>
          <div id="pag-errors" class="pagination"></div>
        </div>
        <table><thead><tr><th>时间</th><th>级别</th><th>消息</th></tr></thead><tbody id="tb-errors"><tr><td colspan="3" style="color:var(--dim)">暂无异常</td></tr></tbody></table>
      </div>
    </div>
  </div>
</aside>
<div class="drawer-backdrop" id="drawer-backdrop" aria-hidden="true"></div>
```

- [ ] **Step 6: 运行契约测试确认通过**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py::test_render_dashboard_html_contains_case_drawer_contract -v`
Expected: PASS

- [ ] **Step 7: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 8: Commit**

```bash
git add src/api/dashboard_page/partials/view_dashboard.html tests/test_dashboard_page_contract.py
git commit -m "feat: extract case-shell into case-drawer container"
```

---

## Task 2: CSS — drawer 滑出样式 + 遮罩

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css` (在 `.dashboard-shell` 之前添加)

**Success Criteria:**
- `.case-drawer` 是 position: fixed，初始 transform: translateX(100%) 隐藏在右侧
- `.case-drawer.open` 触发 transform: translateX(0) 滑入
- 滑入动画时长 0.3s，缓动函数 ease
- `.drawer-backdrop` 是 fixed inset:0 半透明黑色背景
- `.drawer-backdrop.open` 显示
- Drawer 头部有 44px 高度，关闭按钮 32x32px
- z-index: drawer 1000, backdrop 999

- [ ] **Step 1: 在 dashboard.css 顶部添加 drawer 基础样式**

在 `dashboard.css` 第 75 行（`.dashboard-shell {` 之前）插入：

```css
/* ═══════════════════════════════════════════════
   CASE DRAWER (案件视图滑出层)
   ═══════════════════════════════════════════════ */

.case-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 50vw;
  max-width: 720px;
  height: 100vh;
  background: var(--panel);
  border-left: 1px solid var(--stroke);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.3s ease;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.case-drawer.open {
  transform: translateX(0);
}

.case-drawer-head {
  flex: 0 0 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-md);
  border-bottom: 1px solid var(--stroke);
  background: var(--panel-2);
}

.case-drawer-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--fg);
  letter-spacing: 0.5px;
}

.drawer-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-close:hover {
  background: var(--hover-bg);
  color: var(--fg);
}

.case-drawer .case-shell {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--space-md);
  height: auto;
  background: transparent;
  border: none;
  display: block;
}

.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 999;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.drawer-backdrop.open {
  opacity: 1;
  pointer-events: auto;
}

@media (max-width: 1024px) {
  .case-drawer {
    width: 60vw;
  }
}

@media (max-width: 768px) {
  .case-drawer {
    width: 100vw;
    max-width: 100vw;
  }
}
```

- [ ] **Step 2: 修改 dashboard-shell 移除 bottom 区域**

在 `dashboard.css` 第 75-85 行找到 `.dashboard-shell` 块，修改为：

```css
.dashboard-shell {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  grid-template-rows: auto 1fr;
  grid-template-areas:
    "top top top"
    "left center right";
  min-height: calc(100vh - 36px);
  gap: 0;
}
```

（即删除 `grid-template-rows: auto 1fr auto` 中的 `auto`，删除 `grid-template-areas` 中的 `"bottom bottom bottom"` 行）

- [ ] **Step 3: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 4: Commit**

```bash
git add src/api/dashboard_page/styles/dashboard.css
git commit -m "feat: add case-drawer slide-out styles and backdrop"
```

---

## Task 3: CSS — 运行记录 2 列网格 + 高度限制

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css` (.run-center-list 和 .run-card)

**Success Criteria:**
- `.run-center-list` 改为 2 列 grid 布局
- 容器最大高度 400px，超出滚动
- `.run-card` 高度限制 64px，内容超出隐藏
- 卡片 hover 时无变化（仅 active 状态变化）
- 在 1024px 断点下变 1 列（避免过窄）

- [ ] **Step 1: 找到现有 .run-center-list 和 .run-card 样式**

```bash
grep -n "run-center-list\|run-card " src/api/dashboard_page/styles/dashboard.css
```

预期找到 `.run-center-list` (大约 line 320) 和 `.run-card` (大约 line 277)

- [ ] **Step 2: 修改 .run-center-list 为 2 列 grid**

找到 `.run-center-list` 块，替换为：

```css
.run-center-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
  padding: 2px;
}
```

- [ ] **Step 3: 修改 .run-card 限制高度**

找到 `.run-card { ... }` 块（保留所有其他属性），修改为：

```css
.run-card {
  max-height: 64px;
  overflow: hidden;
  text-align: left;
  background: var(--panel-2);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 8px 10px;
  cursor: pointer;
  color: var(--fg);
  font-size: 12px;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 4px;
}
```

（保留原有其他属性，仅添加 max-height 和 overflow，调整 padding 以适应更小的高度）

- [ ] **Step 4: 隐藏卡片 note 区域（节省空间）**

找到 `.run-card-note` 样式，在其后追加：

```css
.run-card-note {
  display: none;
}
```

- [ ] **Step 5: 添加响应式断点**

在 `dashboard.css` 的响应式媒体查询（约 line 540）找到 `@media (max-width: 1024px)` 块，添加：

```css
@media (max-width: 1024px) {
  /* ... 现有规则 ... */
  .run-center-list {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 7: Commit**

```bash
git add src/api/dashboard_page/styles/dashboard.css
git commit -m "feat: compact run-center list to 2-column grid with height limit"
```

---

## Task 4: CSS — skeleton 骨架屏样式

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`

**Success Criteria:**
- `.case-skeleton` 容器有合适的 padding
- `.case-skeleton-bar` 是 12px 高度的渐变背景
- `@keyframes skeleton-shimmer` 实现 shimmer 动画
- 动画时长 1.5s，infinite

- [ ] **Step 1: 在 dashboard.css 末尾添加 skeleton 样式**

在 `dashboard.css` 末尾（`}` 前最后一个 CSS 规则后）追加：

```css

/* ═══════════════════════════════════════════════
   SKELETON LOADER (drawer 加载占位)
   ═══════════════════════════════════════════════ */

.case-skeleton {
  padding: var(--space-md);
}

.case-skeleton-bar {
  height: 12px;
  background: linear-gradient(90deg,
    var(--surface) 0%,
    var(--surface2) 50%,
    var(--surface) 100%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: 4px;
  margin-bottom: 8px;
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

- [ ] **Step 2: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard_page/styles/dashboard.css
git commit -m "feat: add skeleton loader styles for case drawer"
```

---

## Task 5: JS — openCaseDrawer / closeCaseDrawer + selectHistoryRun 集成

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**Success Criteria:**
- `openCaseDrawer()` 函数存在且能添加 `.open` class
- `closeCaseDrawer()` 函数存在且能移除 `.open` class
- `selectHistoryRun` 修改为先调用 `openCaseDrawer()` 再执行现有逻辑
- 点击 close button 调用 `closeCaseDrawer()`
- 点击 backdrop 调用 `closeCaseDrawer()`
- 重复点击同一 run card 不触发重新打开动画（noop）

- [ ] **Step 1: 添加 closeCaseDrawer 函数**

在 `dashboard.js` 顶部（第 11 行 `displayTimeValue` 函数之后）插入：

```javascript
function isCaseDrawerOpen() {
  return document.getElementById('case-drawer')?.classList.contains('open');
}

function openCaseDrawer(runId) {
  var drawer = document.getElementById('case-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  if (drawer.dataset.activeRun === runId && drawer.classList.contains('open')) {
    return;
  }
  drawer.dataset.activeRun = runId;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  backdrop.classList.add('open');
  backdrop.setAttribute('aria-hidden', 'false');
}

function closeCaseDrawer() {
  var drawer = document.getElementById('case-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  backdrop.classList.remove('open');
  backdrop.setAttribute('aria-hidden', 'true');
}
```

- [ ] **Step 2: 修改 selectHistoryRun 调用 openCaseDrawer**

找到 `dashboard.js` 第 1605 行的 `async function selectHistoryRun(runId, options = {})` 函数，在函数开头（第 1611 行 `renderRunCenter` 之后）添加：

```javascript
  selectedHistoryRunMeta = { ...run };
  selectedCaseStage = stagePaneId('overview');
  renderRunCenter(historyRuns, { preserveData: true });
  openCaseDrawer(runId);  // 新增：触发 drawer 滑出
```

（即将原来的 3 行修改为第 1、3、4 行保留，新增 `openCaseDrawer(runId)` 调用）

- [ ] **Step 3: 添加 backdrop 点击关闭监听**

在 `bootstrap.js` 第 142 行（`loadDashboard();` 之前）添加：

```javascript
document.getElementById('drawer-backdrop')?.addEventListener('click', closeCaseDrawer);
```

- [ ] **Step 4: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/scripts/bootstrap.js
git commit -m "feat: add openCaseDrawer/closeCaseDrawer and wire to selectHistoryRun"
```

---

## Task 6: JS — showCaseDrawerSkeleton + ESC 键监听

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**Success Criteria:**
- `showCaseDrawerSkeleton()` 函数存在，渲染 4 条 shimmer bar 到 `#case-shell`
- ESC 键监听在 bootstrap.js 中添加，drawer 打开时按 ESC 关闭
- Skeleton 在 `openCaseDrawer` 后、fetch snapshot 前显示

- [ ] **Step 1: 添加 showCaseDrawerSkeleton 函数**

在 `dashboard.js` 顶部（第 11 行 `displayTimeValue` 函数之前）插入：

```javascript
function showCaseDrawerSkeleton() {
  var shell = document.getElementById('case-shell');
  if (!shell) return;
  shell.innerHTML = '<div class="case-skeleton">' +
    '<div class="case-skeleton-bar" style="width: 40%"></div>' +
    '<div class="case-skeleton-bar" style="width: 70%"></div>' +
    '<div class="case-skeleton-bar" style="width: 60%"></div>' +
    '<div class="case-skeleton-bar" style="width: 80%"></div>' +
    '<div class="case-skeleton-bar" style="width: 30%"></div>' +
    '</div>';
}
```

- [ ] **Step 2: 在 openCaseDrawer 中调用 showCaseDrawerSkeleton**

修改 `dashboard.js` 中 `openCaseDrawer` 函数，在 `backdrop.classList.add('open')` 之后添加：

```javascript
  showCaseDrawerSkeleton();
```

完整的 `openCaseDrawer` 函数变为：

```javascript
function openCaseDrawer(runId) {
  var drawer = document.getElementById('case-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  if (drawer.dataset.activeRun === runId && drawer.classList.contains('open')) {
    return;
  }
  drawer.dataset.activeRun = runId;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  backdrop.classList.add('open');
  backdrop.setAttribute('aria-hidden', 'false');
  showCaseDrawerSkeleton();
}
```

- [ ] **Step 3: 在 bootstrap.js 添加 ESC 键监听**

在 `bootstrap.js` 的 `document.addEventListener('keydown', ...)` 块（第 129 行）中添加 ESC 处理：

```javascript
  if (event.key === 'Escape' && isCaseDrawerOpen()) {
    event.preventDefault();
    closeCaseDrawer();
  }
```

完整的 `keydown` 监听块变为：

```javascript
document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault();
    savePreferences();
  }

  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    if (!simRunning) {
      triggerRun();
    }
  }

  if (event.key === 'Escape' && isCaseDrawerOpen()) {
    event.preventDefault();
    closeCaseDrawer();
  }
});
```

- [ ] **Step 4: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js src/api/dashboard_page/scripts/bootstrap.js
git commit -m "feat: add skeleton loader and ESC key handler for case drawer"
```

---

## Task 7: JS — 简单虚拟滚动（防御性优化）

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**Success Criteria:**
- 引入 `renderRunCenterVirtual` 函数，支持视口 + buffer 渲染
- 16 条记录下回退到完整渲染（虚拟滚动仅在 ≥ 50 条时启用）
- 容器滚动时正确更新可见卡片
- 现有 `renderRunCenter` 保持完整渲染逻辑（小数据量优先）

- [ ] **Step 1: 在 renderRunCenter 之前添加虚拟滚动函数**

在 `dashboard.js` 第 1448 行（`function renderRunCenter(runs, options = {})` 之前）插入：

```javascript
var RUN_CARD_ITEM_HEIGHT = 72;
var RUN_CARD_VIRTUAL_THRESHOLD = 50;

function renderRunCenterVirtual(runs, options) {
  var list = document.getElementById('run-center-list');
  if (!list) return renderRunCenter(runs, options);
  if (runs.length < RUN_CARD_VIRTUAL_THRESHOLD) {
    return renderRunCenter(runs, options);
  }
  var buffer = 4;
  var itemHeight = RUN_CARD_ITEM_HEIGHT;
  var totalHeight = Math.ceil(runs.length / 2) * itemHeight;
  var scrollTop = list.scrollTop;
  var viewportHeight = list.clientHeight;
  var startRow = Math.max(0, Math.floor(scrollTop / itemHeight) - buffer);
  var endRow = Math.min(
    Math.ceil(runs.length / 2),
    Math.ceil((scrollTop + viewportHeight) / itemHeight) + buffer
  );
  var visibleRuns = runs.slice(startRow * 2, endRow * 2);
  var paddingTop = startRow * itemHeight;
  var paddingBottom = totalHeight - endRow * itemHeight;

  if (!options.preserveData) {
    replaceHistoryRuns(runs);
  }
  var filtered = getFilteredHistoryRuns().filter(function(run) {
    var idx = runs.findIndex(function(r) { return r.id === run.id; });
    return idx >= startRow * 2 && idx < endRow * 2;
  });
  list.innerHTML =
    '<div style="height:' + paddingTop + 'px"></div>' +
    filtered.map(renderRunCard).join('') +
    '<div style="height:' + paddingBottom + 'px"></div>';
  if (selectedHistoryRunMeta) {
    list.querySelectorAll('.run-card').forEach(function(card) {
      if (card.dataset.runId === selectedHistoryRunMeta.id) {
        card.classList.add('active');
      }
    });
  }
}
```

- [ ] **Step 2: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 32 passed

- [ ] **Step 3: Commit**

```bash
git add src/api/dashboard_page/scripts/dashboard.js
git commit -m "feat: add simple virtual scroll for run center (50+ records)"
```

**注意：** Task 7 是防御性优化，不影响 16 条数据下的当前行为。可在后续记录增长到 50+ 时启用。

---

## Task 8: 契约测试 + 全量测试验证

**Files:**
- Modify: `tests/test_dashboard_page_contract.py`

**Success Criteria:**
- 至少 4 个新契约测试覆盖 drawer、backdrop、close、ESC 监听
- 全部 36+ 个测试通过

- [ ] **Step 1: 添加 drawer 状态契约测试**

```python
# tests/test_dashboard_page_contract.py (追加)
def test_render_dashboard_html_drawer_not_open_by_default():
    """验证 drawer 默认状态是关闭的（无 open class）"""
    html = render_dashboard_html()
    assert 'id="case-drawer"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'class="case-drawer"' in html
    assert 'class="drawer-backdrop"' in html
    assert 'aria-hidden="true"' in html
```

- [ ] **Step 2: 添加 close 控件测试**

```python
def test_render_dashboard_html_contains_close_button():
    """验证 close 按钮已嵌入"""
    html = render_dashboard_html()
    assert 'id="drawer-close"' in html
    assert 'closeCaseDrawer()' in html
    assert 'aria-label="关闭案件视图"' in html
```

- [ ] **Step 3: 添加 rail-bottom 已删除测试**

```python
def test_render_dashboard_html_rail_bottom_removed():
    """验证 rail-bottom 已被 drawer 取代"""
    html = render_dashboard_html()
    assert 'class="rail-bottom"' not in html
```

- [ ] **Step 4: 添加骨架屏测试**

```python
def test_render_dashboard_html_contains_skeleton_function():
    """验证 skeleton 函数和样式已嵌入"""
    html = render_dashboard_html()
    assert 'showCaseDrawerSkeleton' in html
    assert 'case-skeleton' in html
    assert 'skeleton-shimmer' in html
```

- [ ] **Step 5: 运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`
Expected: 36+ passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_dashboard_page_contract.py
git commit -m "test: add drawer and skeleton contract tests"
```

---

## Task 9: 浏览器验证 + 部署到 AWS

**Files:**
- 无文件改动，仅执行验证和部署

**Success Criteria:**
- 浏览器验证 3 个问题全部解决
- 代码已部署到 AWS 服务器
- 生产环境验证通过

- [ ] **Step 1: 同步文件到 AWS 服务器**

```bash
SSH_KEY="/Users/shenmingjie/.ssh/xingxing.pem"
REMOTE="ec2-user@13.214.201.113"
LOCAL_BASE="/Users/shenmingjie/workSpace/tranding/a-share-hub"
REMOTE_BASE="/home/ec2-user/a-share-hub"

scp -i "$SSH_KEY" "$LOCAL_BASE/src/api/dashboard_page/partials/view_dashboard.html" "$REMOTE:$REMOTE_BASE/src/api/dashboard_page/partials/view_dashboard.html"
scp -i "$SSH_KEY" "$LOCAL_BASE/src/api/dashboard_page/styles/dashboard.css" "$REMOTE:$REMOTE_BASE/src/api/dashboard_page/styles/dashboard.css"
scp -i "$SSH_KEY" "$LOCAL_BASE/src/api/dashboard_page/scripts/dashboard.js" "$REMOTE:$REMOTE_BASE/src/api/dashboard_page/scripts/dashboard.js"
scp -i "$SSH_KEY" "$LOCAL_BASE/src/api/dashboard_page/scripts/bootstrap.js" "$REMOTE:$REMOTE_BASE/src/api/dashboard_page/scripts/bootstrap.js"
```

- [ ] **Step 2: 重启 uvicorn 服务**

```bash
ssh -o ConnectTimeout=10 -i /Users/shenmingjie/.ssh/xingxing.pem ec2-user@13.214.201.113 \
  "pkill -f 'uvicorn src.main' 2>/dev/null; sleep 2; cd /home/ec2-user/a-share-hub && nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 & disown; sleep 3; pgrep -f 'uvicorn src.main'"
```

Expected: 2 个 PID 输出（master + worker）

- [ ] **Step 3: 验证 health**

```bash
curl -s --max-time 10 http://13.214.201.113:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: 浏览器验证 Issue 1 — 点击案件有反应**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh open http://13.214.201.113:8000/dashboard
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh state
# 找到 "完整案件" 卡片的索引
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh click <idx>
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh eval "document.getElementById('case-drawer').classList.contains('open')"
```

Expected: `true`

- [ ] **Step 5: 浏览器验证 Issue 2 — 卡片 2 列布局**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh eval "window.getComputedStyle(document.getElementById('run-center-list')).gridTemplateColumns"
```

Expected: 包含两个像素值（2 列）

- [ ] **Step 6: 浏览器验证 Issue 3 — Tab 切换可点**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh eval "document.querySelectorAll('.case-stage-rail button').length"
```

Expected: 6（概览/决策/目标仓位/订单/对账/异常）

- [ ] **Step 7: 关闭浏览器**

```bash
bash /Users/shenmingjie/.agents/skills/browser-use/scripts/browser-use-local.sh close
```

- [ ] **Step 8: Commit（如有元数据变更）**

如本次为合入 master 的最后一步：

```bash
git push origin master
```

---

## Self-Review

### 1. Spec coverage

| 设计要求 | 覆盖任务 |
|---------|---------|
| HTML 抽取 case-shell 到 drawer | Task 1 |
| Drawer CSS 样式 + 滑出动画 | Task 2 |
| 卡片 2 列网格 + 64px 高度 | Task 3 |
| Skeleton 骨架屏 | Task 4 |
| openCaseDrawer / closeCaseDrawer | Task 5 |
| ESC 键监听 + 遮罩关闭 | Task 5, 6 |
| selectHistoryRun 集成 drawer | Task 5 |
| 简单虚拟滚动（防御性） | Task 7 |
| 契约测试 | Task 8 |
| 浏览器验证 + 部署 | Task 9 |

✓ 所有 5 个组件、3 个验收标准、4 个迁移步骤均已覆盖。

### 2. Placeholder scan

- 无 TBD / TODO
- 无 "implement later"
- 每个 step 都有具体代码或命令
- 函数签名一致（`openCaseDrawer(runId)`, `closeCaseDrawer()`, `isCaseDrawerOpen()`, `showCaseDrawerSkeleton()`）

### 3. Type consistency

- `openCaseDrawer(runId: string)` — 接受 runId 字符串，与 `selectHistoryRun(runId, options)` 一致
- `closeCaseDrawer()` — 无参
- `isCaseDrawerOpen()` — 返回 boolean
- `showCaseDrawerSkeleton()` — 无参，返回 undefined
- DOM 元素 ID 在所有任务中保持一致：`case-drawer`, `drawer-backdrop`, `drawer-close`, `case-shell`

### 4. Scope check

整个计划只涉及 dashboard drawer 重构，未扩展到后端 API、其他视图或左侧/右侧面板。✓

### 5. Ambiguity check

- Drawer 宽度 50vw / max 720px ✓
- 卡片 64px 高度，2 列 grid，max-height 400px ✓
- Skeleton 4-5 条 bar，shimmer 动画 1.5s ✓
- 虚拟滚动阈值 50 条 ✓
- 关闭方式：close button + backdrop + ESC ✓
