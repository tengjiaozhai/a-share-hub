# Alpha Dashboard Layout Refresh Design

> 生成日期：2026-06-01
> 状态：用户已确认采用“方案 1 / 指挥台布局”

---

## 1. 目标

在不改变现有深色工作台色调、不改变 Alpha API 契约、不新增前端框架的前提下，重做 `src/api/dashboard_page/partials/view_alpha.html` 的信息排布，让 Alpha 区从“纵向堆叠的普通表单卡片”变成“人工执行指挥台”。

这次刷新只解决版式、层次和可读性问题，不把范围扩展到功能改造。

---

## 2. 当前问题

当前 `view_alpha.html` 的问题不是颜色，而是结构：

- 所有内容都以同一种 `risk-card` 从上到下堆叠，视觉节奏单一。
- “先看状态，再做动作”的操作顺序没有被版式表达出来。
- 建议单创建、建议单列表、资产状态、观察列表这几种完全不同的信息密度被塞进同一层级。
- `alpha.js` 当前渲染出的资产、建议单、候选列表过于朴素，导致即使外框变好看，内部信息仍会显得像调试输出。

---

## 3. 设计原则

本次设计遵守以下硬约束：

- 保持现有深色工作台气质，继续使用现有根变量色系。
- 不引入新页面入口，不改 `/dashboard` 路由。
- 不改任何现有 API endpoint。
- 不删除或改名以下现有 DOM id：
  - `alpha-execution-mode`
  - `alpha-execution-reason`
  - `alpha-portfolio-summary`
  - `alpha-positions`
  - `alpha-exceptions`
  - `alpha-assets`
  - `alpha-ticket-form`
  - `alpha-symbol`
  - `alpha-underlying`
  - `alpha-qty`
  - `alpha-limit`
  - `alpha-thesis`
  - `alpha-tickets`
  - `alpha-watchlist`
  - `alpha-candidates`
- 保留现有 JS 入口函数：
  - `submitAlphaTicket(event)`
  - `runAlphaScan()`
  - `proposeTopAlphaTicket()`
- 允许对 `src/api/dashboard_page/scripts/alpha.js` 做最小量标记增强，但不改行为语义。

设计原则本身也保持单路径：

- 状态优先于操作。
- 操作优先于浏览。
- 表单与结果相邻，避免用户在首屏上下找回显。
- 布局可以升级，数据权威源不变。

---

## 4. 选定方向：指挥台布局

用户已确认采用“方案 1”：

- 顶部先展示 Alpha Desk 概览与三张状态卡。
- 中部用双栏完成“建议单录入 + 建议单队列”。
- 底部再放“资产状态 + 研究观察与候选”。

这是最符合人工交易工位心智模型的一种结构，页面阅读顺序固定为：

1. 今天能不能动
2. 当前组合和异常有没有阻断
3. 要创建什么建议单
4. 已创建的建议单处于什么状态
5. 当前市场与观察对象是什么

---

## 5. 页面结构

### 5.1 框架

`#view-alpha` 重构为一个带 Hero 区的分层 dashboard，而不是连续卡片流。

建议结构如下：

```text
view-alpha
├─ alpha-hero
│  ├─ hero heading
│  └─ hero summary copy
├─ alpha-status-grid
│  ├─ capability card
│  ├─ portfolio card
│  └─ exceptions card
├─ alpha-ops-grid
│  ├─ ticket composer card
│  └─ ticket queue card
└─ alpha-data-grid
   ├─ assets card
   └─ research card
      ├─ action bar
      ├─ watchlist block
      └─ candidates block
```

### 5.2 Hero 区

Hero 区保留标题 `Alpha 代币化证券`，但增加一行固定说明文字，例如：

- “半自动执行台，先判定执行能力，再录入建议单，再回看资产与候选。”

Hero 不引入大色块，不破坏工作台风格，只通过：

- 更明确的标题分组
- 一行说明文字
- 一条细分隔线
- 轻微背景高光

来建立开场层次。

---

## 6. 区块设计

### 6.1 顶部状态区

顶部做三列状态卡：

1. **Execution Capability**
   - 容器继续使用 `id="alpha-execution-capability"`
   - `alpha-execution-mode` 作为主值
   - `alpha-execution-reason` 作为解释文案

2. **Portfolio Snapshot**
   - `alpha-portfolio-summary` 作为摘要行
   - `alpha-positions` 作为持仓列表

3. **Exceptions**
   - `alpha-exceptions` 作为异常内容区域

这三张卡必须视觉上属于一组：

- 高度接近
- 标签风格统一
- 数据区比标题更显眼
- 异常卡在有异常时允许更强的边框/底色对比

### 6.2 中部操作区

中部是本次刷新最重要的部分，改成 `2fr / 1.3fr` 左右的双栏：

#### 左栏：建议单创建

`alpha-ticket-form` 不再只是几行裸 input，而是一个正式录单面板：

- 顶部标题与辅助说明
- 第一行：`alpha-symbol` / `alpha-underlying`
- 第二行：`alpha-qty` / `alpha-limit`
- 第三行：`alpha-thesis` 大 textarea
- 底部：提交按钮

目标是让用户一眼知道“这是这页最主要的主动操作区”。

#### 右栏：建议单队列

`alpha-tickets` 改成明显的队列卡：

- 标题旁可以有一个只读小计数位
- 空状态单独居中显示
- 有数据时，每条建议单表现为有节奏的横向条目，而不是五个 span 裸排

为了让这一块真的成立，允许在 `alpha.js` 中把每条建议单渲染成更清晰的层次结构，例如：

- 左侧：资产代码 + 标的代码
- 中间：动作、数量、限价
- 右侧：状态 badge

这仍然属于版式升级，不属于行为改造。

### 6.3 底部数据区

底部做双栏：

#### 左栏：资产状态

`alpha-assets` 使用表格感更强的列表块，而不是内联 style 的简单 flex 行。

每条资产行至少区分：

- 资产代码
- 标的代码
- 市场状态
- 资产状态

状态字段应有 badge 感，但不需要新增颜色体系，只使用现有 green / yellow / red / dim 语义。

#### 右栏：观察列表与候选

右栏内部再分成两块：

- 顶部 action bar
  - “运行扫描”
  - “生成建议单”
- 中部 `alpha-watchlist`
- 底部 `alpha-candidates`

`alpha-watchlist` 和 `alpha-candidates` 视觉上不能再混成一个文本大块，而应是两个可独立阅读的列表区。

---

## 7. 视觉语言

### 7.1 保持不变的部分

- 整体 dark theme
- 现有根变量体系
- 页面与工作台其他 tab 的同一视觉家族
- 字体家族不切换，避免和全局页面脱节

### 7.2 新增的版式语言

Alpha 区单独引入以下视觉特征：

- 更强的网格化布局
- 更明显的分区标题
- 卡片内部的双层信息密度
- 柔和内阴影 / 外描边，提升“控制台”而不是“表单页”的感觉
- 更有节奏的空状态区

### 7.3 卡片处理方式

Alpha 专属卡片应与通用 `risk-card` 拉开差异，但仍属于同一个系统：

- 外框更薄
- 圆角略大
- 顶部标签使用更紧的 uppercase 样式
- 数据行之间使用细分隔线
- hover 仅在可操作区域生效，避免全部卡片都“会动”

---

## 8. 需要改动的文件

### 必改

- `src/api/dashboard_page/partials/view_alpha.html`
- `src/api/dashboard_page/styles/dashboard.css`

### 允许的最小配套改动

- `src/api/dashboard_page/scripts/alpha.js`

仅允许做以下类型的配套改动：

- 给 `alpha-tickets` 的每条记录增加更合理的结构层级
- 给 `alpha-assets` / `alpha-watchlist` / `alpha-candidates` 的渲染结果增加 class
- 优化空状态结构

禁止在这次刷新中做以下事情：

- 修改 endpoint
- 改变 fetch 行为
- 新增状态管理
- 更改建议单提交 payload
- 引入任何新依赖

---

## 9. 推荐 DOM 结构

下面是建议的 `view_alpha.html` 轮廓，实施时可以微调，但职责不要变：

```html
<div class="view alpha-desk" id="view-alpha">
  <section class="alpha-hero">
    <div class="alpha-hero-copy">
      <p class="alpha-kicker">Alpha Desk</p>
      <h2>Alpha 代币化证券</h2>
      <p class="alpha-summary">
        半自动执行台，先确认执行能力，再录入建议单，再回看资产与研究候选。
      </p>
    </div>
  </section>

  <section class="alpha-status-grid">
    <article class="alpha-panel" id="alpha-execution-capability">...</article>
    <article class="alpha-panel">...</article>
    <article class="alpha-panel">...</article>
  </section>

  <section class="alpha-ops-grid">
    <article class="alpha-panel alpha-panel-form">...</article>
    <article class="alpha-panel alpha-panel-queue">...</article>
  </section>

  <section class="alpha-data-grid">
    <article class="alpha-panel">...</article>
    <article class="alpha-panel">...</article>
  </section>
</div>
```

重点是新增语义容器，不改现有数据目标节点。

---

## 10. Responsive 规则

桌面端按三段布局。

平板端：

- 顶部状态区变 2 列
- 中部操作区变上下堆叠
- 底部数据区保持 1 列

手机端：

- 所有区域单列
- 表单输入改为全宽顺序布局
- 建议单队列、资产状态、候选列表都要允许纵向滚动

不要求单独设计移动端专属视觉语言，但必须可读、可点击、不卡住表单。

---

## 11. 验收标准

本次设计完成后，必须同时满足：

1. `view_alpha.html` 不再是六张同构 `risk-card` 的纵向堆叠。
2. 首屏能同时看到：
   - Alpha 标题与说明
   - 执行能力
   - 组合摘要
   - 异常状态
3. 首屏中部必须形成“建议单创建 + 建议单队列”的双栏关系。
4. 资产状态与观察列表/候选必须位于底部数据区，而不是继续散落堆叠。
5. `alpha.js` 所依赖的所有现有 id 都仍然可用。
6. 不新增新路由、不新增新 API、不改变现有提交行为。
7. 页面风格仍与当前工作台一致，不引入突兀的新色调。

---

## 12. 非目标

本次不处理：

- Alpha 功能补全
- crypto 视图回归
- 数据模型改造
- 新增确认/审批交互
- 新增图表
- 改写全局工作台设计系统

---

## 13. 自检

- 范围是否过大：否。本设计只覆盖 Alpha 区的排版刷新与必要标记增强。
- 是否和用户要求一致：是。保持工作台色调不变，只重做排版。
- 是否与现有代码契约冲突：否。保留全部现有关键 id 与 handler。
- 是否存在“看起来是样式改动，实际偷偷做架构改动”：否。只允许最小 `alpha.js` 标记增强。
