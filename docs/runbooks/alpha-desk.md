# Alpha 代币化证券操作台 - 操作手册

## 概述

Alpha 操作台当前以持仓分析为主。Dashboard 中的 Alpha 页提供通用股票代码分析入口，并允许直接补充 `持仓仓位 (%)` 与 `买入时间` 作为分析上下文。

Dashboard 不再提供“建议单 + 操作员 + 手动回填成交”的主入口；成交历史与 multi-leg 数据仅保留为只读参考信息。

## API 端点

### 资产数据

```
GET /api/v1/alpha/assets
```

返回代币化证券的公开资产快照列表，包含交易状态、数量限制等信息。

### 建议单

```
POST /api/v1/alpha/tickets          # 创建建议单
GET  /api/v1/alpha/tickets          # 列出所有建议单
POST /api/v1/alpha/tickets/{id}/approve  # 审批建议单
POST /api/v1/alpha/tickets/{id}/fills    # 回填执行结果
```

### 持仓分析报告

```
POST /api/v1/alpha/portfolio/report
```

请求体支持：

- `symbols`
- `position_ratio`
- `buy_time`
- `include_shadow`
- `include_backtest`
- `backtest_window`
- `opening_cash`

### 工作台集成

Alpha 面板已集成到 Dashboard 工作台（`GET /api/v1/dashboard/workbench`）。Dashboard 主入口以分析表单为主，历史成交与 multi-leg 记录作为只读参考显示在同页。

## 典型工作流

1. **查看资产**: 调用 `GET /api/v1/alpha/assets` 确认可分析标的
2. **输入分析上下文**: 在 Dashboard Alpha 页填写股票代码，并按需补充 `持仓仓位 (%)` 与 `买入时间`
3. **生成报告**: 调用 `POST /api/v1/alpha/portfolio/report` 获取持仓、影子建议、回测与综合建议
4. **对照历史**: 在 Alpha 页只读查看最近成交与 multi-leg 历史，辅助理解报告背景

## 测试

运行 Alpha Desk Phase 1 回归测试：

```bash
TEST_DATABASE_URL="postgresql+psycopg://..." /opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_alpha_client.py::test_market_service_normalizes_asset_snapshot \
  tests/test_alpha_routes.py::test_alpha_assets_endpoint_returns_normalized_rows \
  tests/test_alpha_routes.py::test_alpha_ticket_api_supports_create_approve_and_fill \
  tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_ticket_and_manual_fill \
  tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_operations_tab \
  tests/test_dashboard_api.py::test_workbench_payload_includes_alpha_panel \
  -q
```

## 边界说明

- 系统当前以分析为主，不在 Dashboard 主路径中承担人工回填成交录入
- 页面中的成交历史与 multi-leg 历史只用于参考，不作为分析表单输入
- 当前支持的资产来源为 Binance 代币化股票
