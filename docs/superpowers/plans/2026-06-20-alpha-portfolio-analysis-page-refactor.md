# 持仓分析页半重构计划

## Summary

把当前 `Alpha` tab 半重构成真正的 `持仓分析` 页，主流程改为“输入股票代码 -> 结合工作台生成分析”，持仓/成交录入退为辅助区。页面层面移除旧的 Alpha 建议单、资产状态、观察列表、执行能力等用户心智，改成股票代码分析 + 当前持仓 + 成交历史 + 分析报告四块。

这次不做整仓库命名大迁移：后端仍保留现有 `/api/v1/alpha/*` 路径和 `alpha` 模块名，但页签文案、页面结构、前端交互、数据契约都收敛到“持仓分析”语义。

## Key Changes

### 1. 交互与信息架构

- 顶部导航把 `Alpha` 改成 `持仓分析`。
- 原 `view-alpha` 页面重排为两个主区：
  - 主区：股票代码输入、市场识别、生成分析按钮、分析结果卡。
  - 辅助区：当前持仓摘要、分笔成交历史、持仓录入/修正表单。
- 页面移除这些旧 Alpha 区块：
  - 建议单录入
  - 建议单队列
  - 资产状态
  - 观察列表与候选
  - Direct Execution Capability
  - Alpha 异常
- 保留现有“持仓分析报告”能力，但入口从“基于已有持仓生成”改成“基于当前输入代码或已持仓代码生成”。

### 2. 代码优先的数据与接口

- 成交录入从“先建建议单，再回填 fill”改成“直接按股票代码录入成交”。
- 新的 canonical 手工成交输入模型：
  - `symbol`
  - `action`
  - `quantity`
  - `price`
  - `executed_at`
  - `notes`
- `alpha_manual_fills` 不再把 `ticket_id` 作为页面主流程前置条件。
  - `ticket_id` 若保留，只能是可选关联字段，不再是 canonical 身份。
  - 所有持仓重建、成交历史、多段买入统计都以 `symbol + action + quantity + price + executed_at` 为准。
- 新增一个直接录入成交的接口，建议放在现有命名空间下：
  - `POST /api/v1/alpha/portfolio/fills`
- 保留 `GET /api/v1/alpha/portfolio` 和 `POST /api/v1/alpha/portfolio/rebuilds`，但返回语义完全以股票代码持仓为中心。
- 扩展 `POST /api/v1/alpha/portfolio/report`：
  - 支持传入单只或多只 `symbols`
  - 即使当前没有持仓，也能对输入代码生成分析结果
  - 报告结果直接复用工作台影子建议、回测、现价/风险信息

### 3. 股票代码与分析规则

- 支持两类代码输入：
  - A 股：`600519` / `600519.SH` / `000858.SZ`
  - 美股：`AAPL` / `AAPL.US` / `NVDA.US`
- 规范化默认规则：
  - 6 位纯数字优先按 A 股代码解析，再补 `.SH` / `.SZ`
  - 纯英文 ticker 默认按美股处理，规范成 `.US`
- 分析结果统一输出这些 reader-facing 区块：
  - 标的基本信息：规范代码、名称、市场
  - 当前持仓：数量、成本、现价、浮盈亏
  - 工作台意见：最近模拟/影子建议与理由
  - 回测摘要：窗口收益、最大回撤、交易次数
  - 综合动作：`WATCH / HOLD / ADD / REDUCE / EXIT`
- 对“未持仓但输入了代码”的情况，不显示空白报告，必须返回一份代码级分析卡。

### 4. 前端实现收敛

- `view_alpha.html` 改成代码分析优先布局，文案全部去 Alpha 化。
- `alpha.js` 改成两条清晰流程：
  - `analyzeBySymbol(symbol)`：代码规范化 -> 调用报告接口 -> 渲染分析结果
  - `recordHoldingFill(fill)`：直接按股票代码录入成交 -> 刷新持仓摘要/历史
- Dashboard HTML contract tests 更新为新页面标识：
  - 按钮文案是 `持仓分析`
  - 页面标题、表单字段、结果容器都不再出现建议单/Alpha 执行语义
- 旧的 ticket/watchlist/assets/capability 前端调用全部从该页移除。

## Test Plan

- 后端
  - 直接股票代码录入成交后，可重建持仓并生成正确的多段成交历史。
  - `portfolio/report` 对两种情况都能工作：
    - 已持仓代码
    - 未持仓但手动输入的代码
  - A 股与美股代码规范化正确。
- 前端
  - 持仓分析页加载后，主入口是股票代码输入，不再依赖建议单选择。
  - 输入 `600519`、`NVDA` 能渲染分析结果。
  - 录入一笔真实成交后，当前持仓和成交历史会刷新。
- 合约
  - 页签文案从 `Alpha` 变为 `持仓分析`
  - 页面不再包含旧 Alpha 控件标识
  - 现有工作台和 Shadow run 相关测试不被这次页面重构破坏

## Assumptions

- 这次是“用户心智和主流程”的半重构，不做整个后端命名空间改名；`/api/v1/alpha/*` 和 `src/alpha/*` 可保留。
- 旧 Alpha ticket/watchlist/assets 路由不要求在本次彻底删除，但它们必须退出 `持仓分析` 页主流程。
- 页面视觉沿用当前 Dashboard 风格，不走新的视觉 ideation 流程。
- 若 bare 美股代码未带后缀，默认按 `.US` 处理；若 bare A 股代码是 6 位数字，默认按 A 股处理。
