# `dashboard.html` 替换为交易工作台的设计与接口对接方案

## Summary

以 [workbench.html](/Users/shenmingjie/workSpace/tranding/a-share-hub/docs/prototype/workbench.html) 为唯一视觉与交互基准，整体替换 [dashboard.html](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/dashboard.html)，保留其三栏工作台 + 底部回放区结构，不再混用现有静态看板布局。  
后端在 [routes_dashboard.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_dashboard.py) 中收敛为一个聚合读接口和一个同步运行接口，前端去掉 mock 回退、去掉四个散接口拼装、去掉 `run_id` 轮询模型。

## Key Changes

### 1. 页面替换策略

- 直接用原型的五个功能区替换现有首页结构：
  - 顶部状态条
  - 左侧策略配置
  - 中央本轮运行时间线
  - 右侧风控与人工接管
  - 底部历史回放 Tab
- 保留原型的工业终端风格，不回退到当前 `dashboard.html` 的卡片看板风格。
- `dashboard.html` 中必须删除以下原型阶段代码和行为：
  - `runMockFlow()`
  - `pollRunStatus(runId)`
  - `POST /api/v1/dashboard/kill`
  - 对 `status/decisions/orders/portfolio` 四个散接口的并发调用
  - 所有“后端未实现时自动 mock”的分支
- 页面只保留真实生产交互：
  - `loadWorkbench()`
  - `submitRun()`
  - `toggleKillSwitch()`
  - `renderWorkbench(payload)`

### 2. 前端字段与交互收敛

- 左侧配置区保留原型交互，但提交给后端的字段必须标准化，不允许前端继续猜字段名。
- 前端提交体固定为：

```json
{
  "capital_base": 1000000,
  "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
  "max_position_ratio": 0.2,
  "stop_loss_ratio": 0.05,
  "max_daily_loss_ratio": 0.03,
  "allow_new_positions": true,
  "decision_mode": "mock",
  "execution_mode": "full"
}
```

- `watchlist` 是最终股票列表，`手动添加股票` 只是前端便利输入，不单独作为后端字段。
- `止损阈值` 和 `单日最大亏损` 在 UI 上改成正数百分比语义，提交前统一转成小数比率，避免 `-5` / `-3` 的正负号歧义。
- `decision_mode=real` 在 v1 保留视觉位置，但前端置灰禁用；如果强行提交，后端返回 `400`。当前只接 `mock`。
- 中央时间线不再等待轮询，而是直接渲染 `POST /run` 返回的完整结果。
- 底部四个 Tab 的字段固定为：
  - `最近决策`：`symbol / action / confidence / reason / created_at`
  - `最近订单`：`symbol / action / quantity / limit_price / status / created_at`
  - `当前目标仓位`：`symbol / target_value / target_position_ratio / expires_at`
  - `异常事件`：`timestamp / level / message`

### 3. 仪表盘接口重构

- 仪表盘专属接口收敛为两个：
  - `GET /api/v1/dashboard/workbench`
  - `POST /api/v1/dashboard/run`
- 页面直接复用现有停机接口，不再发明 dashboard 私有 kill 接口：
  - `GET /api/v1/kill-switch/status`
  - `POST /api/v1/kill-switch/activate`
  - `POST /api/v1/kill-switch/deactivate`
- 原有 dashboard 散接口 `status / decisions / orders / portfolio` 从页面中彻底移除；如无其他调用方，同步从路由层删除，不保留双轨。

### 4. 聚合读接口契约

`GET /api/v1/dashboard/workbench` 返回首屏完整渲染数据，字段固定如下：

```json
{
  "mode": "shadow",
  "trade_date": "2026-05-26",
  "last_run_at": "2026-05-26T10:15:12Z",
  "services": {
    "database": "ok",
    "llm": "unknown",
    "market": "unknown"
  },
  "kill_switch": {
    "active": false
  },
  "config": {
    "capital_base": 1000000,
    "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
    "max_position_ratio": 0.2,
    "stop_loss_ratio": 0.05,
    "max_daily_loss_ratio": 0.03,
    "allow_new_positions": true,
    "decision_mode": "mock",
    "execution_mode": "full"
  },
  "risk": {
    "concentration_ratio": 0.2,
    "active_target_count": 1,
    "open_orders": 0,
    "alerts": [
      {"timestamp": "2026-05-26T10:15:12Z", "level": "info", "message": "系统就绪，等待运行"}
    ]
  },
  "latest_run": {
    "run_context_id": "wrk-20260526-101512-ab12",
    "started_at": "2026-05-26T10:15:12Z",
    "finished_at": "2026-05-26T10:15:18Z",
    "status": "completed",
    "steps": [
      {
        "stage": "decision",
        "status": "done",
        "timestamp": "2026-05-26T10:15:13Z",
        "items": [{"symbol": "600519.SH", "action": "BUY", "confidence": 80, "reason": "mock output"}]
      },
      {
        "stage": "target",
        "status": "done",
        "timestamp": "2026-05-26T10:15:14Z",
        "items": [{"symbol": "600519.SH", "target_value": 100000, "target_position_ratio": 0.1}]
      },
      {
        "stage": "execute",
        "status": "done",
        "timestamp": "2026-05-26T10:15:16Z",
        "items": [{"symbol": "600519.SH", "action": "BUY", "quantity": 100, "limit_price": 100.0, "status": "FILLED"}]
      },
      {
        "stage": "reconcile",
        "status": "done",
        "timestamp": "2026-05-26T10:15:18Z",
        "message": "open_orders=0, broker_event_count=2, healthy=true"
      }
    ]
  },
  "history": {
    "decisions": [],
    "orders": [],
    "targets": [],
    "events": []
  }
}
```

- 服务状态不允许假装全绿；拿不到真实探针时返回 `unknown`，前端渲染黄色。
- `history.events` 统一输出为 UI 可直接渲染的事件流，不让前端自己拼 `kill_switch` 与 broker 异常。

### 5. 同步运行接口契约

- `POST /api/v1/dashboard/run` 使用与 `GET /workbench` 相同的 `config` 字段作为请求体。
- 该接口同步执行一轮 shadow 工作流：
  - 决策
  - 目标仓位生成
  - 执行计划生成
  - 若 `execution_mode=full`，继续生成执行订单与 broker 事件
  - 对账摘要生成
- 返回值直接复用 `GET /api/v1/dashboard/workbench` 的完整 payload 结构，前端收到后直接整体重渲染。
- `execution_mode=decision` 时：
  - `latest_run.steps` 只返回 `decision`、`target`
  - `execute`、`reconcile` 不生成伪步骤
- `kill_switch.active=true` 时：
  - 返回 `200` 或 `409` 都可以，但响应体必须是完整 workbench payload
  - `latest_run.status="blocked"`
  - `latest_run.steps` 仅包含一个 `blocked`/`decision` 前置步骤
  - 顶部和右栏同步出现阻断提示
- 不引入 `run_id`、状态表、轮询接口。

### 6. 运行链路持久化方式

- 为了满足“刷新页面后保留最近一轮时间线”，本轮运行引入一个轻量 `run_context_id`，但不新增 `dashboard_runs` 表。
- `run_context_id` 写入 `decision_input_snapshots.payload_json.market_context.run_context_id`。
- `GET /workbench` 恢复最新时间线时，按下面链路重建：
  - `decision_runs`：通过 snapshot 中的 `run_context_id`
  - `target_positions`：通过 `decision_run_id`
  - `execution_orders`：通过 `target_position_id`
  - `broker_events`：通过 `execution_order_id`
- `execution_plan` 阶段不单独持久化为页面依赖对象，时间线可由该轮 `target_positions` 合成展示，避免再加一条新的关联链。
- 若一次运行在 preflight 阶段就被 `kill switch` 阻断，不覆盖已持久化的 `latest_run`；阻断信息只出现在本次响应和 `alerts` 中。

## Test Plan

- 打开 `/dashboard`，首屏结构必须与原型一致，且不再出现旧版资产卡片、持仓表和图表占位。
- `GET /api/v1/dashboard/workbench` 在空库场景下返回：
  - `latest_run.status="idle"`
  - 四个历史表为空
  - `alerts` 至少有一条 `系统就绪`
- `POST /api/v1/dashboard/run` 在 `execution_mode=full` 时返回四阶段完整时间线。
- `POST /api/v1/dashboard/run` 在 `execution_mode=decision` 时不返回执行与对账伪数据。
- 激活 `kill switch` 后：
  - `GET /workbench` 显示停机状态
  - `POST /run` 返回 `blocked`
  - 主按钮变灰或不可点击
- 页面刷新后，`GET /workbench` 能恢复最近一轮 `latest_run.steps`，不是只保留底部历史表。
- `decision_mode=real` 在 UI 中不可选；若 API 收到该值，明确报错，不静默降级为 `mock`。
- 服务状态字段为 `unknown` 时，顶部状态点显示黄色，不允许写死绿色。

## Assumptions

- 不保留 dashboard 专属旧散接口兼容；页面完成切换后，`dashboard.html` 只依赖 `GET /workbench`、`POST /run` 和现有 `kill-switch` API。
- 不保留任何前端 mock 回退逻辑；后端未就绪时直接 fail-fast。
- 不展示“总资产 / 今日盈亏 / 持仓市值”这类当前仓库无法真实计算的指标。
- v1 仅支持 `shadow + mock decision`，`real` 只是未来占位，不在本次接通。
