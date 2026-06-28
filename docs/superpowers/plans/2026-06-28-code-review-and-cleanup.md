# 代码审查与清理总结 (2026-06-28)

## 目标
- 代码审查 + 清理 + 架构优化
- 基金板块调研与数据源接入

## 已完成的工作

### 1. Alpha 持仓单路径收敛

**问题**: `load_portfolio()` 从 `manual_fills + tickets` 拼工作台返回值，但实际写入入口是 `holdings entries`，导致读写路径不一致。

**修复**:
- `src/alpha/portfolio_service.py`: `load_portfolio()` 现在直接从 `alpha_holdings_entries` 生成 `fills` 和 `fills_by_symbol`
- 保留 `rebuild_from_manual_fills()` 以兼容旧测试
- 更新相关测试锁定新行为

**文件**:
- `src/alpha/portfolio_service.py`
- `tests/test_alpha_portfolio_service.py`
- `tests/test_alpha_holdings.py`
- `tests/test_dashboard_api.py`

### 2. 基金代码归一化支持

**问题**: `infer_exchange()` 只认股票前缀，基金 6 位代码（如 `512650`, `159707`）会抛 `unsupported stock code`。

**修复**:
- `src/data/providers/akshare_catalog.py`: 添加已验证的基金前缀支持
  - `511/512 -> SH` (ETF)
  - `159/166 -> SZ` (ETF/LOF)
- 更新 `alpha/symbols.py` 的归一化逻辑
- 添加测试锁定行为

**文件**:
- `src/data/providers/akshare_catalog.py`
- `tests/test_akshare_catalog.py`
- `tests/test_alpha_symbols.py`
- `tests/test_akshare_history.py`
- `tests/test_alpha_routes.py`

### 3. Yahoo Finance NaN 处理

**问题**: `yf.download()` 返回部分字段为 `NaN` 时，`int(NaN)` 会进入 `parse failed`，把整条报价退化成空对象。

**修复**:
- `src/us_stock/yahoo_provider.py`: 添加 `_safe_float()` 和 `_safe_int()` 辅助函数
- 批量 quote 解析使用 NaN-safe 转换
- 添加 `_get_yahoo_provider()` seam 以支持测试
- 添加测试锁定行为

**文件**:
- `src/us_stock/yahoo_provider.py`
- `src/us_stock/routes.py`
- `tests/us_stock/test_yahoo_provider.py`

### 4. 文档收敛

**问题**: README、架构文档和 runbook 仍引用已删除的 Alpha API（`/api/v1/alpha/assets`, `/tickets`, `/portfolio/report` 等）。

**修复**:
- `README.md`: 移除旧 API 引用，更新为当前 live API
- `docs/architecture.md`: 更新 Alpha 流程描述
- `docs/runbooks/alpha-desk.md`: 更新操作手册

**文件**:
- `README.md`
- `docs/architecture.md`
- `docs/runbooks/alpha-desk.md`

### 5. 其他修复

- `src/api/routes_alpha.py`: 修复 A 股回测分支的坏导入（`src.a_stock.akshare_provider` -> `src.data.providers.akshare_provider`）
- `tests/test_dashboard_page_contract.py`: 更新过期的 dashboard 合同测试

## 验证结果

所有相关测试通过：
```
112 passed in 35.77s
```

包括：
- Alpha 持仓相关测试
- 基金代码归一化测试
- Yahoo Finance NaN 处理测试
- Dashboard 合同测试
- API 路由测试

## 未完成的清理项

以下代码只在测试中使用，不在生产代码中使用，但删除它们需要更多工作：

1. **Alpha 旧 ticket/fill 方法**:
   - `src/storage/runtime_store.py`: `insert_alpha_ticket`, `insert_alpha_manual_fill`, `list_alpha_tickets`, `list_alpha_manual_fills`, `list_all_alpha_manual_fills`
   - 这些方法在多个测试文件中使用，删除需要重构测试

2. **Alpha execution 模块**:
   - `src/alpha/execution_gateway.py`
   - `src/alpha/execution_models.py`
   - `src/alpha/execution_service.py`
   - 只在 `tests/test_alpha_execution_service.py` 中使用

3. **Alpha reconciliation 模块**:
   - `src/alpha/reconciliation.py`
   - 只在 `tests/test_alpha_reconciliation.py` 中使用

这些模块的删除需要评估是否会影响未来的功能计划，建议作为独立的清理任务处理。

## 基金板块调研结论

- `akshare` 可以做主要上游，但不能直接当"单一统一基金源"
- ETF/LOF 和开放式基金必须分流
- 现有 symbol 规则已放行基金代码（`511/512 -> SH`, `159/166 -> SZ`）
- 最小接入面分别在：
  - `src/data/providers/base.py`
  - `src/api/routes_market.py`
  - `src/alpha/market_price_service.py`
  - `src/alpha/symbols.py`

## 下一步建议

1. **基金功能落地**: 基于当前归一化支持，添加基金目录 service 和 route
2. **旧代码清理**: 评估并删除未使用的 alpha execution/reconciliation 模块
3. **测试重构**: 将使用旧 ticket/fill 方法的测试迁移到新的 holdings entries 模型

### 6. 未使用的服务模块

以下模块在生产代码中没有被使用：

1. **`src/data/market_snapshot_service.py`**: `MarketSnapshotService` 类只在定义处出现，没有被导入或使用
2. **`src/execution/execution_plan_service.py`**: `build_execution_plan()` 函数没有被任何代码调用

这些模块可以安全删除，但建议作为独立的清理任务处理，以避免影响测试。

## 代码审查发现

### 高优先级问题

1. **Alpha 双路径问题** (已修复): `load_portfolio()` 和 `holdings entries` 读写路径不一致
2. **基金代码归一化失败** (已修复): 基金 6 位代码无法通过 `infer_exchange()`
3. **Yahoo Finance NaN 处理** (已修复): 批量 quote 解析时 `int(NaN)` 导致整条报价丢失

### 中优先级问题

1. **文档与代码不一致** (已修复): README 和架构文档引用已删除的 API
2. **坏导入** (已修复): `routes_alpha.py` 中 `src.a_stock.akshare_provider` 不存在

### 低优先级问题

1. **未使用的服务模块**: `MarketSnapshotService` 和 `build_execution_plan()` 没有被使用
2. **旧测试方法**: 多个测试文件仍使用旧的 ticket/fill 方法

## 架构优化建议

1. **统一数据提供者抽象**: 当前 `AkshareProvider` 和 `YahooProvider` 有不同的接口和错误处理方式，建议统一
2. **基金功能分层**: 基于当前归一化支持，可以分三层实现基金功能：
   - 第一层：ETF/LOF 行情（复用现有 quote/history 路径）
   - 第二层：基金目录（新增 fund catalog service）
   - 第三层：开放式基金净值（新增 fund NAV service）
3. **测试重构**: 将使用旧 ticket/fill 方法的测试迁移到新的 holdings entries 模型

## 基金板块调研详细结论

### 可用的 akshare 接口

1. **基金目录**: `ak.fund_name_em()` - 返回基金代码/简称/类型总目录
2. **ETF 实时行情**: `ak.fund_etf_spot_em()` - 可用但慢（单次调用约十几秒）
3. **ETF 历史行情**: `ak.fund_etf_hist_em(symbol=..., period="daily", ...)` - 部分代码返回空
4. **LOF 行情**: `ak.fund_lof_spot_em()` 和 `ak.fund_lof_hist_em(symbol=..., period="daily", ...)`
5. **开放式基金净值**: `ak.fund_open_fund_info_em(symbol=..., indicator="单位净值走势")` - 可用
6. **净值估算**: `ak.fund_value_estimation_em(symbol="全部")` - 字段带日期，不适合作为稳定内部 schema

### 风险

1. **仓库内 symbol 规则不支持基金裸代码** (已修复)
2. **当前 catalog 只认股票，不认基金** (已修复)
3. **AkShare 基金接口是分裂的，不是统一 schema**
4. **稳定性风险**: `fund_etf_spot_em()` 慢，`fund_open_fund_daily_em()` 不稳，`fund_etf_hist_em()` 对部分代码返回空

### 结论

- **如果范围仅限 ETF/LOF 基础行情**: 勉强可用，但仍有覆盖风险
- **如果范围包含基金目录 + 开放式基金净值 + ETF 行情**: 不建议把 AkShare 当成"单一稳定数据源"直接依赖
- **更稳妥的结论**: AkShare 可以做主要上游，但仓库内必须自己做基金类型分流、字段归一化和失败策略
