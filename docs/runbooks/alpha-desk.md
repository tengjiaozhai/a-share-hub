# Alpha 代币化证券操作台 - 操作手册

## 概述

Alpha 操作台用于管理代币化证券（Tokenized Securities）的建议单流程。系统提供公开资产数据查询、建议单创建/审批、人工执行结果回填等功能。

**当前版本不支持自动下单**，所有交易执行需人工操作后回填结果。

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

### 工作台集成

Alpha 面板已集成到 Dashboard 工作台（`GET /api/v1/dashboard/workbench`），返回数据中的 `alpha` 字段包含建议单列表。

## 典型工作流

1. **查看资产**: 调用 `GET /api/v1/alpha/assets` �认可交易标的
2. **创建建议单**: 调用 `POST /api/v1/alpha/tickets` 提交交易建议
3. **审批**: 由操作员调用 `POST /api/v1/alpha/tickets/{id}/approve`
4. **人工执行**: 操作员在交易所手动下单
5. **回填结果**: 调用 `POST /api/v1/alpha/tickets/{id}/fills` 记录执行价格和数量

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

- 系统仅提供"建议"，不自动执行交易
- 所有执行结果通过人工回填
- 当前支持的资产来源为 Binance 代币化股票
