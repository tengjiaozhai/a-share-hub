# a-share-hub 移动端适配改造计划

> **架构师**: GLM-5.2（智谱）  
> **协作**: Hermes Agent（qwen3.7-plus）协调 + 调研报告 + mobile-responsiveness/ui-density skills  
> **日期**: 2026-07-11  
> **策略**: 渐进增强，不破坏现有桌面体验

> 量化交易系统的移动端不是"缩小版桌面"，而是**场景重构**——桌面是"分析+执行"一体，移动端是"监控+快速响应"，深度操作仍回桌面。

---

## 1. 设计原则

| # | 原则 | 说明 |
|---|------|------|
| P1 | **场景分层** | 移动端聚焦"行情监控 + 快速下单 + 持仓管理"，复杂策略配置、回测、深度分析保留为桌面优先 |
| P2 | **密度可切换** | 通过 `data-density` 属性 + CSS 变量，同一组件支持三档密度，power user 可在移动端手动切到"紧凑" |
| P3 | **渐进式披露** | 默认低密度摘要，关键指标常驻，次级数据通过 tap/swipe 展开抽屉/Sheet |
| P4 | **触控优先，键鼠兼容** | 移动端 `pointer: coarse` 关闭 hover-only 交互，桌面保留快捷键 |
| P5 | **SSR 友好** | 不引入 SPA 框架，用纯 CSS + 少量原生 JS（IntersectionObserver / matchMedia）实现交互 |
| P6 | **零布局抖动** | 保留 Grid 骨架，移动端用 `display: none` + 抽屉替代，避免 CLS |
| P7 | **安全区域优先** | 底部 Tab Bar 必须避开 iOS Home Indicator，顶部避开刘海 |
| P8 | **深色主题不变** | 仅调整对比度，移动端户外强光下需更高对比度（WCAG AAA 文本） |

---

## 2. 断点策略

```css
/* 移动优先断点定义 */
--bp-mobile:  768px;   /* < 768: 单栏, 低密度 */
--bp-tablet: 1024px;  /* 768-1023: 双栏, 中密度 */
--bp-desktop: 1280px; /* 1024-1279: 三栏紧凑, 高密度 */
--bp-wide:   1536px;  /* >= 1280: 三栏完整, 高密度 */
```

| 断点 | 范围 | 栏数 | 密度 | 触控目标 | 主要设备 |
|------|------|------|------|----------|----------|
| `xs` | < 768 | 1 | 低 (56px row) | 44px | 手机竖屏 |
| `sm` | 768–1023 | 2 | 中 (44px row) | 40px | 平板/手机横屏 |
| `md` | 1024–1279 | 3 紧凑 | 高 (32px row) | 32px | 小屏笔记本 |
| `lg` | ≥ 1280 | 3 完整 | 高 (32px row) | 32px | 桌面 |

**实现策略**：移动优先写法 + `min-width` 媒体查询向上增强，避免桌面端 2164 行 CSS 大改。

---

## 3. 布局改造（三栏 → 移动端）

### 3.1 桌面现状（≥ 1280px）
```
┌────────┬──────────────────────┬──────────┐
│ 左栏    │   中栏（图表+盘口）   │  右栏    │
│ 自选    │                      │  下单    │
│ Watchlist│                      │  持仓    │
│ 240px  │   1fr                │  320px   │
└────────┴──────────────────────┴──────────┘
```

### 3.2 平板（768–1023px）
```
┌────────────┬──────────────────────────────┐
│ 左栏(抽屉)  │      中栏（图表+盘口）        │
│ ← 滑出     │                              │
│            │  ┌──────────────────────┐    │
│            │  │  底部 Tab: 行情/下单/持仓 │    │
│            │  └──────────────────────┘    │
└────────────┴──────────────────────────────┘
```

### 3.3 移动端（< 768px）
```
┌──────────────────────────────┐
│ 顶栏: [☰]  贵州茅台  ¥1685  ⋮ │  ← 粘性顶栏 + 安全区
├──────────────────────────────┤
│                              │
│   主内容区（单栏滚动）         │
│   - 行情摘要卡                │
│   - 迷你 K 线                 │
│   - 五档盘口（折叠）          │
│                              │
├──────────────────────────────┤
│ [行情] [交易] [持仓] [我的]   │  ← 底部 Tab Bar
└──────────────────────────────┘
       ↑ env(safe-area-inset-bottom)
```

### 3.4 关键交互
- **汉堡菜单**：左上角 ☰ → 滑出抽屉（自选列表、策略、设置）
- **底部 Tab Bar**：4 个主场景切换，对应 SSR 不同路由
- **浮动下单按钮（FAB）**：行情页右下角，一键弹出下单 Sheet
- **Sheet 组件**：从底部滑入，遮罩 60% 透明度，下滑关闭
- **横屏增强**：`orientation: landscape` 且 < 768 时，恢复双栏（图表+盘口）

---

## 4. 功能优先级矩阵

| 功能 | 桌面 | 平板 | 移动 | 移动入口 | 备注 |
|------|------|------|------|----------|------|
| 实时行情（价格/涨跌） | P0 | P0 | P0 | 顶栏 + 主区 | 常驻可见 |
| 快速下单（限价/市价） | P0 | P0 | P0 | FAB → Sheet | 2 步内完成 |
| 持仓查看 | P0 | P0 | P0 | Tab3 | 含盈亏 |
| 自选股列表 | P0 | P1 | P1 | 抽屉 | 默认折叠 |
| K 线图 | P0 | P0 | P1 | 主区迷你 + 全屏 | 双指缩放 |
| 五档盘口 | P0 | P1 | P1 | 折叠卡 | tap 展开 |
| 委托/成交查询 | P1 | P1 | P2 | Tab3 子页 | 分页加载 |
| 策略配置 | P0 | P2 | P3 | 提示"建议桌面" | 仅查看 |
| 回测 | P0 | P2 | × | × | 桌面专属 |
| 资金流水 | P1 | P2 | P2 | "我的"页 | |
| 预警通知 | P1 | P1 | P0 | 系统通知 + 红点 | 移动核心 |
| 账户设置 | P1 | P1 | P2 | "我的"页 | |

**P0 = 常驻可见，P1 = 1 次交互可达，P2 = 2 次交互，P3 = 仅查看，× = 不支持**

---

## 5. 密度 Token CSS 变量

```css
:root {
  /* ===== 密度 Token ===== */
  /* 行高 */
  --row-height-dense: 32px;       /* 桌面高密度 */
  --row-height-normal: 44px;      /* 平板中密度 */
  --row-height-comfortable: 56px; /* 移动低密度 */

  /* 字号 */
  --font-size-dense: 12px;
  --font-size-normal: 14px;
  --font-size-comfortable: 16px;
  --font-size-label: 11px;
  --font-size-data: 13px;        /* 数字用等宽 */

  /* 间距 */
  --space-dense: 4px;
  --space-normal: 8px;
  --space-comfortable: 12px;
  --space-section: 16px;

  /* 触控目标 */
  --touch-target-min: 44px;
  --touch-target-dense: 32px;

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* 当前激活密度（默认桌面） */
  --row-height: var(--row-height-dense);
  --font-size-base: var(--font-size-dense);
  --space-base: var(--space-dense);
  --touch-target: var(--touch-target-dense);

  /* 安全区 */
  --safe-top: env(safe-area-inset-top, 0px);
  --safe-bottom: env(safe-area-inset-bottom, 0px);
  --safe-left: env(safe-area-inset-left, 0px);
  --safe-right: env(safe-area-inset-right, 0px);

  /* 深色主题（增强移动端对比度） */
  --bg-base: #0d1117;
  --bg-surface: #161b22;
  --bg-elevated: #1c2128;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --border: #30363d;
  --accent: #2f81f7;
  --up: #3fb950;     /* 涨 */
  --down: #f85149;   /* 跌 */
}

/* 平板 */
@media (max-width: 1023px) {
  :root {
    --row-height: var(--row-height-normal);
    --font-size-base: var(--font-size-normal);
    --space-base: var(--space-normal);
    --touch-target: var(--touch-target-min);
  }
}

/* 移动 */
@media (max-width: 767px) {
  :root {
    --row-height: var(--row-height-comfortable);
    --font-size-base: var(--font-size-comfortable);
    --space-base: var(--space-comfortable);
    --touch-target: var(--touch-target-min);
  }
}

/* power user 手动切换紧凑 */
[data-density="dense"] {
  --row-height: var(--row-height-dense);
  --font-size-base: var(--font-size-dense);
  --space-base: var(--space-dense);
}
```

---

## 6. CSS 改造清单

### 6.1 全局基础（~200 行新增）
- [ ] 引入密度 CSS 变量到 `:root`
- [ ] `meta viewport` 补充 `viewport-fit=cover, maximum-scale=5`
- [ ] `html { -webkit-text-size-adjust: 100%; }`
- [ ] `body { overscroll-behavior: none; }` 防止下拉刷新干扰
- [ ] `* { -webkit-tap-highlight-color: transparent; }`
- [ ] `input, select { font-size: 16px; }` 防 iOS 聚焦放大
- [ ] `:focus-visible` 替代 `:focus`，移动端不显示焦点环

### 6.2 布局 Grid 改造（核心）
```css
/* 原：固定三栏 */
.dashboard-shell {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  grid-template-rows: auto 1fr;
  min-height: calc(100vh - 36px);
}

/* 改：响应式 */
.dashboard-shell {
  display: grid;
  grid-template-columns: 1fr;            /* 移动默认单栏 */
  grid-template-rows: 56px 1fr 64px;     /* 顶栏+主区+TabBar */
  height: 100dvh;                        /* dynamic viewport */
  padding-top: var(--safe-top);
  padding-bottom: var(--safe-bottom);
}

@media (min-width: 768px) {
  .dashboard-shell {
    grid-template-columns: 1fr;
    grid-template-rows: 56px 1fr;
  }
}

@media (min-width: 1024px) {
  .dashboard-shell {
    grid-template-columns: 260px 1fr;
    grid-template-rows: 56px 1fr;
  }
}

@media (min-width: 1280px) {
  .dashboard-shell {
    grid-template-columns: 260px 1fr 280px;
    grid-template-rows: auto 1fr;
    min-height: calc(100vh - 36px);
  }
}
```

### 6.3 组件级改造清单

| 组件 | 改造点 | 行数估算 |
|------|--------|----------|
| 顶栏 status-bar | 粘性 + 安全区 + 汉堡按钮 + 标题缩略 | ~60 |
| 左栏 rail-left | 移动端 `position: fixed; transform: translateX(-100%)` + 遮罩 | ~80 |
| 底部 Tab Bar | `position: fixed; bottom: 0; padding-bottom: var(--safe-bottom)` | ~50 |
| 行情列表 | `row-height` 变量化 + 虚拟滚动兼容 | ~40 |
| K 线图 nav-canvas | 容器 `aspect-ratio: 16/9` + touch-action: none | ~30 |
| 盘口 range-card | 移动端折叠 `details/summary` 或 JS toggle | ~40 |
| 下单面板 | 移动端 Sheet（`position: fixed; bottom: 0`） | ~80 |
| 持仓表格 | 移动端转卡片列表 | ~60 |
| 运行中心 run-card | 单列堆叠 + 滑动删除 | ~40 |
| 抽屉 case-drawer | 已有响应式，微调安全区 | ~20 |
| 流体排版 | `clamp()` 替代固定字号 | ~30 |
| **合计** | | **~530 行新增** |

### 6.4 新增文件清单

| 文件 | 用途 |
|------|------|
| `styles/mobile-base.css` | 全局移动端基础样式（安全区、触控、密度变量） |
| `styles/mobile-layout.css` | 响应式 Grid 布局改造 |
| `styles/mobile-components.css` | 组件级移动端适配 |
| `scripts/mobile-nav.js` | 汉堡菜单 + 底部 Tab + Sheet 交互 |
| `scripts/density-toggle.js` | 密度切换逻辑 |

---

## 7. 分阶段实施计划

### 阶段 1：基础框架（1.5 天）
| 任务 | 工时 | 产出 |
|------|------|------|
| 创建 `mobile-base.css`（密度变量 + 安全区 + 触控优化） | 3h | 全局基础 |
| 修改 `shell.html`（viewport + 新 CSS 引用） | 1h | HTML 骨架 |
| 实现响应式 Grid 布局（`mobile-layout.css`） | 4h | 三栏→单栏转换 |
| 实现汉堡菜单 + 左栏抽屉（`mobile-nav.js`） | 4h | 导航交互 |
| 测试：Chrome DevTools 多设备模拟 | 2h | 基础验证 |

### 阶段 2：核心页面适配（2 天）
| 任务 | 工时 | 产出 |
|------|------|------|
| 底部 Tab Bar 实现 | 3h | 4 场景切换 |
| 选股分析页（view-dashboard）移动端适配 | 4h | 行情卡 + 迷你K线 + 折叠盘口 |
| 持仓分析页（view-alpha）移动端适配 | 3h | 持仓卡片化 |
| A股/美股/基金页移动端适配 | 4h | 列表优化 + 搜索 |
| 流体排版 + 密度切换 | 2h | clamp() + data-density |

### 阶段 3：交互优化（1 天）
| 任务 | 工时 | 产出 |
|------|------|------|
| Sheet 组件（下单面板） | 3h | 底部滑入面板 |
| 滑动手势（左滑删除、右滑刷新） | 3h | 原生 Touch 事件 |
| 横屏增强（landscape 双栏） | 2h | 特殊场景优化 |

### 阶段 4：测试验收（0.5 天）
| 任务 | 工时 | 产出 |
|------|------|------|
| 真机测试（iOS Safari + Android Chrome） | 2h | 兼容性验证 |
| 性能优化（CLS < 0.1, FID < 100ms） | 1h | 性能达标 |
| 无障碍检查（WCAG 2.1 AA） | 1h | 可访问性 |

**总计：5 天**

---

## 8. 验收 Checklist

### 布局
- [ ] 手机竖屏（375px）：单栏，无水平滚动
- [ ] 手机横屏（812px）：双栏或增强布局
- [ ] 平板（768-1023px）：双栏，左栏可折叠
- [ ] 桌面（≥1280px）：三栏完整，与现有体验一致
- [ ] 无 CLS（Cumulative Layout Shift < 0.1）

### 触控
- [ ] 所有可点击区域 ≥ 44×44px
- [ ] 无 hover-only 交互（移动端有替代方案）
- [ ] 输入框 font-size ≥ 16px（防 iOS 缩放）
- [ ] 无 300ms 点击延迟

### 安全区域
- [ ] 底部 Tab Bar 避开 iOS Home Indicator
- [ ] 顶部内容避开刘海/动态岛
- [ ] `viewport-fit=cover` 生效

### 密度
- [ ] 三档密度可切换（default / dense / spacious）
- [ ] Power user 可手动切到 dense
- [ ] 移动端默认 comfortable 密度

### 功能
- [ ] P0 功能在移动端 2 步内可达
- [ ] 策略配置/回测在移动端显示"建议桌面"提示
- [ ] 预警通知在移动端可达

### 性能
- [ ] 新增 CSS < 50KB（gzip 后）
- [ ] 新增 JS < 10KB（gzip 后）
- [ ] 首屏加载 < 2s（4G 网络）
- [ ] 无布局抖动（CLS < 0.1）

### 兼容性
- [ ] iOS Safari 15+
- [ ] Android Chrome 90+
- [ ] 微信内置浏览器（X5 内核）
- [ ] 桌面 Chrome/Firefox/Safari 无回归

---

## 附录：多模型协作记录

| 模型 | 角色 | 贡献 |
|------|------|------|
| **GLM-5.2** | 架构设计 | 设计原则、布局方案、功能矩阵、实施计划 |
| **qwen3.7-plus** | 技术协调 | 调研数据整理、skill 内容提取、代码示例验证 |
| **Hermes Agent** | 编排 | 任务分解、API 调度、文件管理 |
