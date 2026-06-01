# Alpha Execution Capability Gate Runbook

## 概述

Alpha Execution Capability Gate 是 Phase 4 的安全门控机制，确保只有在所有前置条件满足后才允许执行 API 下单。本文档描述了启用 Alpha 执行能力的完整流程和检查步骤。

## 前置条件

### 1. 公开交易接口文档稳定可用

在启用 API 执行模式前，必须确认：
- 目标交易所的 API 文档已发布且版本稳定
- API 端点格式、认证方式、签名算法已确认
- 交易对的精度、最小/最大数量限制已明确

### 2. 环境变量配置

在 `.env` 文件中配置以下变量：

```bash
# Alpha 执行模式：manual（默认）或 api
ALPHA_EXECUTION_MODE=manual

# API 基础 URL（api 模式必填）
ALPHA_API_BASE_URL=https://api.example.com

# API 密钥（api 模式必填）
ALPHA_API_KEY=your_api_key_here

# API 密钥（api 模式必填）
ALPHA_API_SECRET=your_api_secret_here
```

**重要：** 默认模式为 `manual`，所有下单操作需要人工确认。

## 执行流程

### 步骤 1：检查 Capability 状态

首先调用 capability 端点确认当前状态：

```bash
curl -s http://127.0.0.1:8000/api/v1/alpha/capabilities | jq .
```

**预期响应：**

```json
{
  "execution_mode": "manual",
  "api_configured": false,
  "capability": "disabled",
  "reason": "Execution mode is manual"
}
```

**检查要点：**
- `execution_mode` 应为 `manual`（默认）或 `api`
- `api_configured` 应为 `true`（当模式为 `api` 时）
- `capability` 应为 `enabled`（所有条件满足时）

### 步骤 2：验证 Preview 端点

在启用 submit 前，必须先通过 preview 端点验证：

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/orders/preview \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "alpha-ticket-001",
    "asset_symbol": "AAPLx",
    "action": "BUY",
    "quantity": 1.0,
    "limit_price": 210.0
  }' | jq .
```

**预期响应（capability disabled 时）：**

```json
{
  "status": "rejected",
  "reason": "Alpha execution capability is disabled",
  "preview": {
    "ticket_id": "alpha-ticket-001",
    "asset_symbol": "AAPLx",
    "action": "BUY",
    "quantity": 1.0,
    "limit_price": 210.0
  }
}
```

**检查要点：**
- 响应包含 `status` 字段
- 字段格式与 API 文档一致
- 签名算法（如有）计算正确

### 步骤 3：启用 API 执行模式（可选）

如需启用 API 执行模式：

1. 更新 `.env` 文件：
   ```bash
   ALPHA_EXECUTION_MODE=api
   ALPHA_API_BASE_URL=https://api.example.com
   ALPHA_API_KEY=your_actual_key
   ALPHA_API_SECRET=your_actual_secret
   ```

2. 重启服务：
   ```bash
   # 停止当前服务
   pkill -f "src.main serve"
   
   # 启动服务
   /opt/anaconda3/envs/py311/bin/python3 -m src.main serve
   ```

3. 验证 capability 状态：
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/alpha/capabilities | jq .
   ```

   **预期响应：**
   ```json
   {
     "execution_mode": "api",
     "api_configured": true,
     "capability": "enabled",
     "reason": "Alpha execution API mode is active"
   }
   ```

### 步骤 4：验证 Submit 端点

**重要：** 只有在 preview 验证通过后，才允许开放 submit 端点。

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/orders/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "alpha-ticket-001",
    "asset_symbol": "AAPLx",
    "action": "BUY",
    "quantity": 1.0,
    "limit_price": 210.0
  }' | jq .
```

**预期响应（capability enabled 时）：**

```json
{
  "status": "submitted",
  "order_id": "ord_123456",
  "ticket_id": "alpha-ticket-001"
}
```

## 安全原则

### Fail-Closed 原则

- 默认情况下，所有执行能力处于禁用状态
- 只有当所有前置条件满足时，才启用执行能力
- 任何配置错误或 API 不可用都会导致能力被禁用

### 审计日志

所有 API 下单尝试都会记录到运行时存储：
- 时间戳
- 请求参数
- 响应结果
- 执行状态

### 人工确认模式

在 `manual` 模式下：
- Preview 端点返回订单预览
- Submit 端点返回 409 Conflict
- 所有操作需要人工确认

## 故障排查

### 问题：Capability 状态为 disabled

**可能原因：**
1. `ALPHA_EXECUTION_MODE` 未设置或为 `manual`
2. `ALPHA_API_BASE_URL` 未配置
3. `ALPHA_API_KEY` 或 `ALPHA_API_SECRET` 未配置

**解决步骤：**
1. 检查 `.env` 文件配置
2. 重启服务
3. 重新检查 capability 状态

### 问题：Preview 端点返回 500

**可能原因：**
1. API 端点格式错误
2. 签名算法实现错误
3. 网络连接问题

**解决步骤：**
1. 检查服务日志
2. 验证 API 文档
3. 测试网络连接

### 问题：Submit 端点返回 409

**可能原因：**
1. Capability 处于 disabled 状态
2. 未通过 preview 验证

**解决步骤：**
1. 先调用 capability 端点确认状态
2. 调用 preview 端点验证订单格式
3. 确认所有配置正确后重试

## 测试命令

运行 Phase 4 核心测试：

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_config_env.py::test_settings_expose_alpha_execution_configuration \
  tests/test_alpha_execution_service.py::test_execution_service_blocks_submit_when_mode_is_manual \
  tests/test_alpha_execution_service.py::test_execution_service_submits_order_when_api_mode_is_enabled \
  tests/test_alpha_runtime_store.py::test_runtime_store_persists_alpha_api_order_attempt \
  tests/test_alpha_routes.py::test_alpha_capabilities_report_manual_mode \
  tests/test_alpha_routes.py::test_alpha_submit_returns_409_when_capability_disabled \
  tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_execution_capability_panel \
  -q
```

**预期结果：** 7 passed

## 相关文档

- [Alpha Desk 运行手册](alpha-desk.md)
- [Alpha 账本与对账](alpha-ledger-and-reconciliation.md)
- [基础设施负载门控](infrastructure-load-gate.md)
