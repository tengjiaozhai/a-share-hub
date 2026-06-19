# Dashboard 操作体感修复计划

## Summary
目标是把 `/dashboard` 从"能看数据"改成"能操作、能追踪、能解释"。本次按一个权威路径修改，不保留旧交互：运行记录改为可增量加载；净值曲线改为可读的收益视图；区间切换真正驱动数据；模拟交易完成后刷新运行记录；案件视图的决策、目标仓位、订单、对账、异常 tab 必须可点击且有明细。

## Key Changes
- 最近运行记录：后端 `/api/v1/dashboard/history` 增加 `cursor` 和 `has_more/next_cursor`，初始只取 20 条；前端增加"加载更多"和底部滚动触发追加，按 `created_at + id` 去重，保留当前筛选与选中案件。
- 净值曲线：保留现有 canvas 轻量实现，但补齐坐标轴、起止净值、区间收益、最大回撤、最新日期、峰值/低点标记和空数据状态；曲线标题明确当前窗口，例如 `近30天净值`，避免只画一条无上下文的线。
- 区间表现对比：把 `7d/30d/90d/YTD` 从静态按钮改成当前窗口控制；点击后更新 active 状态、调用 `/performance?window=...`、重绘净值曲线，并在 `range-data` 显示该窗口收益、样本天数、起止日期。
- 运行后刷新：`POST /api/v1/dashboard/runs` 已经先写入 summary；前端在 `run.accepted` 时临时插入运行卡，在 `run.completed/run.failed` 后调用 `loadHistoryPanel(market, { prependRunId })` 重新拉取 history，确保记录数和状态立即更新。
- 案件视图 tabs：修正 `switchTab` 只影响当前案件区域，避免误清全局 `.tab-pane`；阶段按钮切换后同步 `selectedCaseStage`，重新渲染 active pane；各 pane 使用同一个 `selectedCaseSnapshot.history/latest_run` 数据源展示决策、目标仓位、订单、对账、异常明细。
- 流式观感：SSE 每个 `stage.updated` 都追加到 live timeline，而不是只覆盖当前阶段；最终 `workbench` 快照只做 reconcile，不能把实时步骤清空或折叠成一次性结果。

## Interface / Contract
- `GET /api/v1/dashboard/history?market=a&account_kind=auto&source=all&limit=20&cursor=...` 返回 `{ runs, has_more, next_cursor }`；`cursor` 由后端生成，前端不解析内部结构。
- `GET /api/v1/dashboard/performance?market=a&account_kind=auto&window=7d|30d|90d|ytd` 返回现有字段，并补充 `window`, `start_date`, `end_date`, `sample_count`, `window_return`；`comparison_cards` 仍用于展示全部区间表现。
- 案件明细仍以 `GET /api/v1/dashboard/workbench?run_context_id=...` 为唯一权威来源，不新增第二套详情接口。

## Test Plan
- API 测试：history 分页第一页/下一页/去重顺序；manual run 在 accepted 后可查，在 completed 后状态和 count 更新；performance 不同 window 返回不同曲线和窗口元数据。
- 前端契约测试：页面包含 load-more 控件、range 按钮绑定、case-stage pane、SSE 追加渲染标记；禁止恢复旧 `/api/v1/dashboard/run` 路径。
- 浏览器验证：打开 `http://13.214.201.113:8000/dashboard`，确认初始运行记录最多 20 条、加载更多追加不重复、区间切换曲线变化、点击案件 tab 显示对应表格、模拟交易完成后新记录出现在顶部。
- 最小命令：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q`。

## Assumptions
- 运行记录采用"加载更多 + 接近底部自动加载"的混合方式；比纯无限滚动更适合交易操作台，因为用户仍能明确知道什么时候追加数据。
- 不引入大型图表库；当前页面是原生 HTML/CSS/JS，先用 canvas + 明确标注解决可读性，避免为一个曲线引入新依赖。
- 自动运行只有概要数据时仍可展示卡片，但案件 tab 只对 `supports_case_view=true` 的手动/可解释运行开放。
