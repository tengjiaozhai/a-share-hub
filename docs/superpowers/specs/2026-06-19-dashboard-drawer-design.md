# Dashboard Drawer 重构设计

> **For:** Dashboard 案件视图可见性 + 运行记录紧凑化
> **Date:** 2026-06-19
> **Status:** Design — awaiting user approval
> **Approach:** 方案 A — 保守重构（复用现有 case-shell 到 drawer）

---

## Summary

Dashboard 当前的 `grid-template-rows: auto 1fr auto` 布局把案件视图（`.case-shell`）推到了页面最底部，导致用户点击运行记录卡片后虽然 `selectHistoryRun` 正常执行但**视觉上没有反馈**。同时中间列的 run-center list 卡片垂直堆叠，使得主仪表盘中间列过高、左右两列显得空旷。

本设计将案件视图从 `rail-bottom` 抽取为独立的 `case-drawer` 容器（position: fixed 覆盖右侧 50%），复用现有 stage rail、pane、snapshot、switchTab 逻辑。同时将运行记录卡片紧凑化（2 列网格 + 高度限制）并加入 skeleton 加载状态和简单虚拟滚动。

---

## Problem Statement

### 当前问题

1. **点击案件无反应（可见性问题）**
   - `selectHistoryRun(runId)` 正确执行，调用 `WORKBENCH_API?run_context_id=...` 加载 snapshot
   - 案件视图在 `.rail-bottom` 容器里，位于 `grid-template-areas: "bottom bottom bottom"`
   - 用户点击后看不到任何变化（被推到了页面最底部，视口外）
   - 体感上像是"点击没反应"

2. **运行记录列表占用过多垂直空间（布局问题）**
   - `.rail-center` 包含：自动运行状态 + 净值曲线 + 区间表现对比 + 最近运行记录
   - run-center 卡片垂直堆叠，16 条记录 × 100px ≈ 1600px
   - 中心列过高，left (260px) + right (280px) 显得空旷
   - 不符合"控制台面板"应有的密集信息呈现

3. **案件视图 Tab 切换不可达（联动问题）**
   - 因问题 1，`.case-stage-rail` 在视口外
   - 即使 `switchTab` 正确执行 `case-stage-pane.active` 切换，用户看不到
   - 体感上是"点击没反应"

### 用户影响

- 点击 run card 后等待 1-2 秒无视觉反馈，怀疑功能坏了
- 滚动到页面底部才能看到案件详情，操作路径长
- 切 Tab 看明细体验差
- 整体 Dashboard 视觉重心不平衡

---

## Goals

1. **G1** — 点击 run card 后立即在视口内显示案件详情
2. **G2** — 主仪表盘不再被案件视图撑高，左右列视觉平衡
3. **G3** — 案件 Tab (决策/目标仓位/订单/对账/异常) 可达且数据正确显示
4. **G4** — 运行记录列表紧凑化，主仪表盘滚动距离 ≤ 1 屏
5. **G5** — 保持现有所有功能不变（filter、search、load more、cursor pagination、case snapshot 加载）

---

## Non-Goals

- 不重写案件视图的渲染逻辑（renderCaseSnapshot、renderTimeline 等保留）
- 不修改后端 API 契约
- 不引入新的前端框架（继续使用 vanilla JS）
- 不重构左侧策略配置面板和右侧 KPI 面板
- 不实现完整虚拟滚动算法（仅渲染视口 + 上下 4 个 buffer 卡片）

---

## Architecture

### 布局变化

**Before:**
```
.dashboard-shell {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  grid-template-rows: auto 1fr auto;
  grid-template-areas:
    "top    top    top"
    "left   center right"
    "bottom bottom bottom";   ← 案件视图在此
}
```

**After:**
```
.dashboard-shell {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  grid-template-rows: auto 1fr;        ← 移除 bottom 行
  grid-template-areas:
    "top    top    top"
    "left   center right";              ← 案件视图从 grid 中抽离
}

.case-drawer {                          ← 独立 fixed 容器
  position: fixed;
  right: 0; top: 0;
  width: 50vw;
  height: 100vh;
  z-index: 1000;
  background: var(--bg);
  transform: translateX(100%);
  transition: transform 0.3s ease;
}
.case-drawer.open { transform: translateX(0); }
```

### 容器抽取

**HTML 结构变化**（`view_dashboard.html`）：

```html
<!-- Before: case-shell 在 rail-bottom 内 -->
<section class="rail-bottom">
  <div class="case-shell">...</div>
</section>

<!-- After: case-shell 抽到顶级 body 直属，rail-bottom 删除 -->
<aside class="case-drawer" id="case-drawer" aria-label="案件视图">
  <div class="case-drawer-head">
    <button class="drawer-close" onclick="closeCaseDrawer()">×</button>
  </div>
  <div class="case-shell" id="case-shell">
    <!-- 内部结构完全复用现有 case-header / case-overview / case-stage-rail / case-stage-grid -->
  </div>
</aside>
<div class="drawer-backdrop" id="drawer-backdrop" onclick="closeCaseDrawer()"></div>
```

### 数据流

```
用户点击 run card
  ↓
selectHistoryRun(runId)
  ├─ selectedHistoryRunMeta = { ...run }
  ├─ renderRunCenter()                    // 高亮当前卡片
  ├─ openCaseDrawer(runId)                // 新增：drawer 滑出
  │   ├─ showCaseDrawerSkeleton()         // 新增：显示骨架屏
  │   └─ fetch WORKBENCH_API?snapshot
  │       └─ renderActiveCase()           // 复用现有逻辑
  │           └─ renderCaseSnapshot()      // 复用现有逻辑
  │               └─ 替换 skeleton 为真实数据
```

Drawer 打开时：
- `.case-drawer` 添加 `.open` class → CSS `translateX(0)` 触发滑入动画
- `.drawer-backdrop` 显示 → 点击空白关闭 drawer
- 关闭按钮 / ESC 键 / 遮罩点击 → `closeCaseDrawer()` → 移除 `.open` class

---

## Components

### Component 1: Case Drawer Container

**职责：** 提供案件视图的滑出容器，包含 head (close button) + shell (复用现有 case-shell)

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `src/api/dashboard_page/styles/dashboard.css`

**接口：**
- HTML: `<aside class="case-drawer" id="case-drawer">...</aside>`
- CSS: `.case-drawer`, `.case-drawer.open`, `.case-drawer-head`, `.drawer-close`, `.drawer-backdrop`

### Component 2: Drawer Controller

**职责：** 控制 drawer 打开/关闭、状态管理、与 selectHistoryRun 联动

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**接口：**
- `openCaseDrawer(runId)` — 打开 drawer 并触发快照加载
- `closeCaseDrawer()` — 关闭 drawer
- `isCaseDrawerOpen()` — 查询状态
- ESC 键监听：`keydown` event → if open, close
- Backdrop 点击：click event → close

**状态：** 复用现有 `selectedHistoryRunMeta`, `selectedCaseSnapshot`, `selectedCaseStage`

### Component 3: Run Card Compact Grid

**职责：** 将 run-center list 改为 2 列网格，卡片高度限制 64px

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`

**CSS：**
```css
.run-center-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}
.run-card {
  max-height: 64px;
  overflow: hidden;
  /* 保留现有样式，仅调整高度 */
}
```

**权衡：** 64px 高度下，需要确保状态、PnL、计数等关键信息仍可见。可隐藏 description（"mock · full" 之类），保留头部 + badge。

### Component 4: Skeleton Loader

**职责：** Drawer 打开后、snapshot 返回前显示骨架屏

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**CSS：**
```css
.case-skeleton { padding: 16px; }
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

**JS：**
```javascript
function showCaseDrawerSkeleton() {
  const shell = document.getElementById('case-shell');
  shell.innerHTML = '<div class="case-skeleton">' +
    '<div class="case-skeleton-bar" style="width: 40%"></div>' +
    '<div class="case-skeleton-bar" style="width: 60%"></div>' +
    '<div class="case-skeleton-bar" style="width: 80%"></div>' +
    '<div class="case-skeleton-bar" style="width: 30%"></div>' +
    '</div>';
}
```

### Component 5: Simple Virtual Scroll (Optional for 16 records)

**职责：** 限制渲染的卡片数量，避免 100+ 记录时 DOM 过大

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

**算法：**
- 容器固定高度 400px
- 卡片高度 64px + gap 8px = 72px per row
- 视口可见行数 ≈ 5.5 → 约 6 行
- 上下各 buffer 4 行 → 总共渲染约 14 个卡片
- 滚动时计算 scrollTop / itemHeight，渲染对应切片

**实现：**
```javascript
function renderRunCenterVirtual(runs, options = {}) {
  const container = document.getElementById('run-center-list');
  if (!container) return;
  const itemHeight = 72;
  const buffer = 4;
  const totalRows = Math.ceil(runs.length / 2);
  const scrollTop = container.scrollTop;
  const viewportHeight = container.clientHeight;
  const startIdx = Math.max(0, Math.floor(scrollTop / itemHeight) - buffer);
  const endIdx = Math.min(totalRows, startIdx + Math.ceil(viewportHeight / itemHeight) + buffer * 2);
  // 渲染 startIdx..endIdx 行的卡片 + 顶部/底部 padding 撑起总高度
}
```

**注意：** 16 条记录的当前规模下，完整渲染也无明显性能问题。此功能作为**防御性优化**，当记录数 ≥ 50 时才发挥作用。

---

## Data Flow

### Drawer 打开流程

```
1. 用户点击 run card (#28 ~ #43)
   onclick: selectHistoryRun('wrk-20260619-...')

2. selectHistoryRun(runId)
   ├─ 找到 run metadata, 设置 selectedHistoryRunMeta
   ├─ renderRunCenter() → 卡片 active 高亮
   └─ openCaseDrawer(runId)
       ├─ document.getElementById('case-drawer').classList.add('open')
       ├─ document.getElementById('drawer-backdrop').classList.add('open')
       ├─ showCaseDrawerSkeleton()
       └─ if run.supports_case_view:
           ├─ fetch WORKBENCH_API?run_context_id=...
           ├─ selectedCaseSnapshot = body
           └─ renderActiveCase() → 替换 skeleton
       else:
           └─ renderCaseEmptyState()

3. 用户与 drawer 交互
   ├─ 点击 close button → closeCaseDrawer()
   ├─ 点击 backdrop → closeCaseDrawer()
   ├─ 按 ESC 键 → closeCaseDrawer()
   └─ 点击 stage rail button → switchTab() 切换 pane (现有逻辑)
```

### Drawer 关闭流程

```
closeCaseDrawer()
  ├─ document.getElementById('case-drawer').classList.remove('open')
  └─ document.getElementById('drawer-backdrop').classList.remove('open')
```

关闭时**不销毁**案件数据，selectedHistoryRunMeta 保留，再次打开同一卡片可立即显示。

---

## Error Handling

| 错误场景 | 处理方式 |
|---------|---------|
| snapshot API 失败 | 现有 `renderCaseEmptyState(error.message)` 处理，drawer 仍显示错误状态 |
| 用户点击概要卡片 | 现有 `renderActiveCase()` 渲染概要视图（不支持案件） |
| drawer 打开后切换 market | 不关闭 drawer，下次刷新时按新 market 加载 |
| 重复点击同一卡片 | 不重新打开，避免动画抖动（noop） |
| 重复点击不同卡片 | 替换 skeleton + 重新加载 snapshot |

---

## Testing

### 单元测试 (Contract Tests)

新增契约测试验证 HTML/JS 契约：

```python
def test_render_dashboard_html_contains_case_drawer_contract():
    """验证 drawer 容器和关闭控件已嵌入"""
    html = render_dashboard_html()
    assert 'id="case-drawer"' in html
    assert 'class="case-drawer"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'class="drawer-close"' in html or 'drawer-close' in html
    assert 'openCaseDrawer(' in html
    assert 'closeCaseDrawer(' in html


def test_render_dashboard_html_drawer_replaces_rail_bottom():
    """验证 rail-bottom 已被移除，drawer 取代"""
    html = render_dashboard_html()
    assert 'class="rail-bottom"' not in html or html.count('class="rail-bottom"') == 0
    # case-shell 仍然存在但移到 drawer 内
    assert 'class="case-shell"' in html
```

### 集成验证 (Browser)

使用 browser-use 脚本验证：

1. 打开 dashboard
2. 点击任一 `完整案件` 卡片
3. 验证 `.case-drawer.open` class 存在
4. 验证 `.case-drawer` 的 `transform` 计算样式为 `translateX(0px)` 或 `matrix(1, 0, 0, 1, 0, 0)`
5. 验证 backdrop 可见
6. 点击 close 按钮 → drawer 滑回
7. 切换 stage rail (决策 → 目标仓位) → 验证 pane 切换
8. 验证 run-center list 是 2 列布局（computed grid-template-columns）

### 回归测试

- 现有 32 个测试必须全部通过
- 测试覆盖：filter、search、load more、cursor pagination、selectHistoryRun

---

## Migration Path

### Step-by-Step Rollout

1. **Step 1 — HTML 结构抽取** (约 30 min)
   - 从 `view_dashboard.html` 删除 `.rail-bottom` 容器
   - 在文件末尾（view-dashboard 关闭 `</div>` 之前）添加 `.case-drawer` + `.drawer-backdrop`
   - 内部 `.case-shell` 内容完全复用现有结构

2. **Step 2 — CSS 改造** (约 60 min)
   - 添加 `.case-drawer` 基础样式 + `.open` 状态
   - 添加 `.drawer-backdrop` 样式
   - 添加 `.run-center-list` 2 列网格
   - 添加 `.run-card` 高度限制
   - 添加 `.case-skeleton` skeleton 样式
   - 修改 `.dashboard-shell` grid 移除 bottom 区域

3. **Step 3 — JS 逻辑** (约 60 min)
   - 添加 `openCaseDrawer(runId)`, `closeCaseDrawer()`, `isCaseDrawerOpen()`
   - 修改 `selectHistoryRun` 调用 `openCaseDrawer`
   - 添加 `showCaseDrawerSkeleton()`
   - 添加 ESC 键监听
   - 可选：虚拟滚动实现

4. **Step 4 — 测试** (约 30 min)
   - 添加契约测试
   - 浏览器验证
   - 回归测试

**总工作量：~3 小时**

### 风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| case-shell DOM 移到 drawer 后，case-stage-rail 内的 `onclick="switchTab(this, 'case-pane-...')"` 仍能工作 | 低 | 验证 click 事件冒泡到 .case-shell |
| grid-template-areas 修改后响应式断点 (mobile) 可能错位 | 中 | 检查 768px / 1024px 断点 |
| 卡片 64px 高度可能让信息过密 | 低 | hover 时可显示完整 description |
| 虚拟滚动引入复杂度 | 低 | 16 条数据下 fallback 到完整渲染 |

---

## Success Criteria

- [ ] 点击 run card → drawer 立即滑出（≤ 300ms 动画）
- [ ] Drawer 内显示完整案件信息（决策/目标仓位/订单/对账/异常）
- [ ] Drawer 关闭方式：close button、backdrop 点击、ESC 键
- [ ] Run-center list 2 列布局，每张卡片高度 ≤ 64px
- [ ] 主仪表盘滚动距离 ≤ 1 屏（中间列内容填满，不超出右栏高度）
- [ ] 32 个测试全部通过
- [ ] 浏览器验证：所有 3 个问题修复
- [ ] 响应式：在 1024px 宽度下布局正常（drawer 可能需要调整为 60% 宽度）

---

## Open Questions

- 是否需要在 drawer 打开时同时锁定 body 滚动？(考虑：drawer 内有自己的滚动条，主页面是否仍可滚动？)
- 移动端 (< 768px) 布局：drawer 应占满全宽
- 卡片 64px 高度下是否需要 hover 显示更多详情？

这些问题在实施阶段细化。

---

## References

- 现有代码: `src/api/dashboard_page/partials/view_dashboard.html:209-317` (case-shell)
- 现有 JS: `src/api/dashboard_page/scripts/dashboard.js:1605-1639` (selectHistoryRun)
- 现有 CSS: `src/api/dashboard_page/styles/dashboard.css:75-85` (dashboard-shell grid)
- 上一轮 UX 优化: `docs/superpowers/plans/2026-06-19-dashboard-ux-issues-implementation.md`
