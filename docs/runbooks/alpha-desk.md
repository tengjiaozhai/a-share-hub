# Alpha 持仓分析台 - 操作手册

## 概述

Alpha 操作台当前以持仓分析为主。Dashboard 中的 Alpha 页提供多标的、多批次持仓录入，并支持对单个标的启动流式分析。

Dashboard 不再提供“建议单 + 操作员 + 手动回填成交”的主入口；成交历史与 multi-leg 数据仅保留为只读参考信息。

## API 端点

### 持仓录入

```
GET    /api/v1/alpha/holdings
POST   /api/v1/alpha/holdings
PUT    /api/v1/alpha/holdings/{entry_id}
DELETE /api/v1/alpha/holdings/{entry_id}
GET    /api/v1/alpha/holdings/summary
```

用于维护已保存的持仓录入，并查询按市场聚合的持仓摘要。

### 持仓分析

```
POST /api/v1/alpha/analysis-runs
GET  /api/v1/alpha/analysis-runs
GET  /api/v1/alpha/analysis-runs/{run_id}
GET  /api/v1/alpha/analysis-runs/{run_id}/events
```

`POST /api/v1/alpha/analysis-runs` 返回 `202 Accepted`，响应体包含 `run_id` 与 `stream_url`。分析阶段为：

- `accepted`
- `snapshot`
- `research`
- `trader`
- `risk`
- `backtest`
- `completed` / `failed`

### 工作台集成

Alpha 面板已集成到 Dashboard 工作台（`GET /api/v1/dashboard/workbench`）。Dashboard 页面会同时展示：

- 当前组合快照
- 已保存持仓录入
- 分析中心历史摘要
- 只读的成交历史与 multi-leg 记录

## 典型工作流

1. **录入持仓**：在 Dashboard Alpha 页维护 stock card 和批次，或直接调用 `POST /api/v1/alpha/holdings`
2. **确认摘要**：调用 `GET /api/v1/alpha/holdings/summary` 或在页面查看当前持仓汇总
3. **启动分析**：从页面点击“分析”，或调用 `POST /api/v1/alpha/analysis-runs`
4. **跟踪阶段**：通过 SSE `GET /api/v1/alpha/analysis-runs/{run_id}/events` 观察阶段推进
5. **复盘历史**：通过 `GET /api/v1/alpha/analysis-runs` 与右侧抽屉查看分析详情，并对照只读成交历史

## 测试

运行当前 Alpha 持仓分析回归测试：

```bash
TEST_DATABASE_URL="postgresql+psycopg://..." /opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_alpha_routes.py \
  tests/test_alpha_analysis_routes_v2.py \
  tests/test_dashboard_alpha_tab.py \
  tests/test_dashboard_page_contract.py \
  -q
```

## 边界说明

- 系统当前以分析为主，不在 Dashboard 主路径中承担人工回填成交录入
- 页面中的成交历史与 multi-leg 历史只用于参考，不作为持仓录入输入
- 页面当前不会提交任何真实订单
