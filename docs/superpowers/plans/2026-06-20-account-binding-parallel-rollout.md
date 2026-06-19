# 账户绑定改造并行实施计划

**日期**: 2026-06-20
**目的**: 将 a-share-hub 从"全局单租户 + 中间件弱鉴权"改造为"按用户隔离业务数据 + 强鉴权"
**基线**: `a4fc144 feat: 更新登录页背景图片`
**架构参考**: Clean Architecture（外层依赖内层、领域不依赖框架）、DDD 战术模式（聚合根 = 用户、Repository 按 user_id 过滤）

---

## 1. 背景

经审计：
- **storage 层 19 张表无任何 user_id/owner_id/tenant 字段**；paper_ledger 5 张表有 `account_id` 但按 `(market, account_kind)` 隔离，是 paper-trading 概念，不是用户身份
- **所有路由 handler 不读取 `request.state.user`**；认证完全靠 `auth_middleware` 按路径前缀白名单做，存在 4 个未保护前缀（`/api/v1/decision-runs`、`/api/v1/execution-plans`、`/api/v1/portfolio-targets`、`/api/v1/reconciliation`、`/api/v1/kill-switch`、`/api/v1/broker-events`）
- **前端完全靠 HttpOnly cookie** 识别用户，没有任何 user_id 透传

改造分三层并行，三层互不重叠文件所有权：

| Worktree | 分支 | 范围 | 优先级 |
|---|---|---|---|
| 1 | `fix/security-p0-holes` | 仅鉴权加固：中间件白名单 + kill-switch role 门 + broker-events HMAC + `/api/crypto` 前缀修正 | **P0** |
| 2 | `feat/user-bound-watchlists` | 仅 watchlist 数据：a_stock/us_stock/alpha 三张自选表 + user_preferences 加 user_id；引入 `Depends(get_current_user)` 依赖 | **P1（最小可用）** |
| 3 | `feat/full-account-binding` | 剩余全量绑定：除 watchlist/偏好外的 16 张表全部加 user_id；RuntimeStore 剩余方法全部接受 user_id；routes_dashboard/decision_runs/execution_plans/portfolio_targets/reconciliation/kill_switch/crypto/alpha/agents 全部注入 get_current_user；paper_ledger 扩 user_id | **P2** |

**merge 顺序**：先 `fix/security-p0-holes`（P0 安全），再 `feat/user-bound-watchlists`，最后 `feat/full-account-binding`。Worktree 2/3 互不重叠，按顺序 merge 即可，无冲突。

---

## 2. Worktree 1: `fix/security-p0-holes`（P0 安全加固）

### 文件所有权（独占）

| 文件 | 改动 |
|---|---|
| `src/api/auth_security.py` | 扩展 `PROTECTED_PREFIXES`；新增 `Depends(require_role)` 依赖；新增 HMAC 验签工具 |
| `src/api/routes_kill_switch.py` | activate/deactivate handler 加 `Depends(require_role("admin"))` |
| `src/api/routes_broker_events.py` | POST handler 加 HMAC 验签（`X-Broker-Signature` header + `BROKER_HMAC_SECRET` 配置） |
| `src/api/routes_crypto.py` | 统一改为 `/api/v1/crypto` 前缀（同时在中间件白名单补回 `/api/v1/crypto`） |
| `src/core/config.py` | 新增 `broker_hmac_secret: str = ""` 配置项 |

### 验收标准

- [ ] `curl http://13.214.201.113:8000/api/v1/kill-switch/activate` 返回 401/403，不再 200
- [ ] `curl http://13.214.201.113:8000/api/v1/decision-runs` 返回 401
- [ ] `curl http://13.214.201.113:8000/api/v1/broker-events` 无签名头返回 401
- [ ] `curl http://13.214.201.113:8000/api/v1/crypto/status` 返回 401（修复前缀）
- [ ] 单元测试覆盖：HMAC 验签失败场景、role 检查场景

### 不动

- 任何 storage 表的 schema
- 任何 RuntimeStore 方法签名
- 任何 watchlist 相关文件
- paper_ledger

---

## 3. Worktree 2: `feat/user-bound-watchlists`（最小可用）

### 文件所有权（独占）

| 文件 | 改动 |
|---|---|
| `src/storage/models.py` | `AStockWatchlistRow` / `USStockWatchlistRow` / `AlphaWatchlistItemRow` / `UserPreferenceRow` 增加 `user_id` 列（不可空 + 索引） |
| `alembic/versions/YYYYMMDD_000013_*.py` | 新增迁移脚本 |
| `src/a_stock/watchlist.py` | `AShareWatchlistStore` 所有方法接受 `user_id`，查询 `WHERE user_id = %s` |
| `src/us_stock/watchlist.py` | `USStockWatchlistStore` 同上 |
| `src/alpha/*`（仅 watchlist 相关 service） | 注入 user_id |
| `src/storage/runtime_store.py` | 仅修改 `get_preference` / `set_preference` 方法，键改为 `{key}:{user_id}` 命名空间 |
| `src/a_stock/routes.py` | 所有 watchlist handler 加 `Depends(get_current_user)`，从 user 取 user_id |
| `src/us_stock/routes.py` | 同上 |
| `src/api/routes_alpha.py` | watchlist 相关 handler 同上 |
| `src/api/routes_dashboard.py` | `GET/PUT /api/v1/dashboard/preferences` handler 加 `Depends(get_current_user)`，preferences key 加 user 后缀 |

### 新增文件

- `src/api/dependencies.py` — 公共 `get_current_user` 依赖（不与 auth_security 现有 `get_current_user_from_request` 冲突）

### 验收标准

- [ ] 用户 A 登录后 add 自选股 `600519.SH`，用户 B 登录 GET 看不到
- [ ] 用户 A 改 theme_id，用户 B 不受影响
- [ ] 用户 A 改 watchlist 配置，用户 B 配置保留
- [ ] alembic upgrade head 迁移成功，老数据迁移到一个默认 user（或要求清理）
- [ ] 单元测试覆盖 user 隔离场景

### 不动

- `src/api/auth_security.py`（由 Worktree 1 独占）
- `src/api/routes_kill_switch.py`、`routes_broker_events.py`、`routes_crypto.py`（由 Worktree 1 独占）
- 任何非 watchlist 的 storage 表
- paper_ledger
- decision_runs / target_positions / execution_plans / orders / accounts_snapshots 等（由 Worktree 3 独占）

---

## 4. Worktree 3: `feat/full-account-binding`（全量绑定）

### 文件所有权（独占）

| 文件 | 改动 |
|---|---|
| `src/storage/models.py` | **除 Worktree 2 拥有的 4 张表外**，其余 15 张表加 `user_id`：ExecutionPlanRow / BrokerEventRow / KillSwitchRow / KillSwitchEventRow / DecisionRunRow / DecisionInputSnapshotRow / TargetPositionRow / ExecutionOrderRow / RiskGateEventRow / AccountSnapshotRow / AlphaTicketRow / AlphaManualFillRow / AlphaPositionRow / AlphaPortfolioSnapshotRow / AlphaReconciliationRunRow / AlphaApiOrderAttemptRow / DashboardRunSummaryRow / DashboardRunEventRow（注：broker_events / kill_switch 已 Worktree 1 触碰，本 worktree 只加 user_id 列） |
| `alembic/versions/YYYYMMDD_000014_*.py` | 新增迁移脚本 |
| `src/storage/runtime_store.py` | **除 `get_preference/set_preference` 已由 Worktree 2 改** 外，所有 50+ 方法签名加 `user_id: str`，所有 SQL WHERE 加 `user_id = %s` |
| `src/paper_ledger/models.py` | 5 张表加 `user_id`（独立迁移） |
| `src/paper_ledger/store.py` | 全部方法接受 `user_id`，并改造 `account_id` 定位为 `(user_id, market, account_kind)` 三元组 |
| `src/paper_ledger/backfill.py` | 注入 user_id |
| `src/scheduler/daily_scheduler.py` | 调用 store 时传入当前 user（保留 system user 概念） |
| `src/api/routes_dashboard.py` | **除 preferences handler 已由 Worktree 2 改** 外，其余 handler 全部加 `Depends(get_current_user)` |
| `src/api/routes_decision_runs.py` | 全部加 `Depends(get_current_user)`，handler 从 user 取 user_id 透传 |
| `src/api/routes_execution_plans.py` | 同上 |
| `src/api/routes_portfolio_targets.py` | 同上 |
| `src/api/routes_reconciliation.py` | 同上 |
| `src/api/routes_alpha.py` | **除 watchlist handler 已由 Worktree 2 改** 外，其余 handler 加 `Depends(get_current_user)` |
| `src/api/routes_market.py` | 全 GET，公开数据，无需 user 隔离（仅确认受保护） |
| `src/api/routes_*.py` 其余 | 全部加 `Depends(get_current_user)` |

### 注意事项

- **system user 概念**：scheduler 触发的自动任务需要"系统级"用户，建议引入 `SYSTEM_USER_ID = "system"` 常量
- **broker_events**：Worktree 1 加 HMAC 验签，本 worktree 加 user_id 列。HMAC 来源（券商） ≠ user，但记录所属 broker
- **kill_switch**：Worktree 1 加 role=admin 检查，本 worktree 给 `kill_switch_events` 加 `actor_user_id` 记录操作人

### 验收标准

- [ ] 用户 A 创建 decision_run，用户 B 看不到
- [ ] 用户 A 创建 target_position，用户 B 看不到
- [ ] 用户 A 触发 dashboard run，A 的 SSE 流 B 无法订阅
- [ ] 用户 A 的 paper_ledger auto 账户 vs 用户 B 完全隔离
- [ ] scheduler 触发的自动 run 标记为 `system` user
- [ ] 单元测试 + 集成测试通过

### 不动

- `src/api/auth_security.py`（Worktree 1 独占）
- `src/a_stock/routes.py`、`src/us_stock/routes.py`（Worktree 2 独占）
- `src/storage/runtime_store.py` 的 `get_preference/set_preference`（Worktree 2 独占）

---

## 5. 集成与合并顺序

```
master (a4fc144)
   │
   ├─► worktree 1  fix/security-p0-holes
   │     └─► 合并 PR #1 (P0，立即)
   │
   ├─► worktree 2  feat/user-bound-watchlists
   │     └─► 合并 PR #2 (P1)
   │
   └─► worktree 3  feat/full-account-binding
         └─► 合并 PR #3 (P2)
```

合并时如果发现 models.py 或 runtime_store.py 冲突，由协调者（当前会话）手动解决——因为各自加的 user_id 在不同表/方法上，**预期无冲突**。

---

## 6. 风险与回滚

- **风险**：迁移脚本无法自动给老数据分配 user_id
  - **缓解**：迁移时把所有历史数据归到 `SYSTEM_USER_ID = "legacy"`，登录后让用户看到自己的"legacy" 数据并提示"请认领"
- **风险**：Scheduler 自动任务找不到 user 上下文
  - **缓解**：使用 `SYSTEM_USER_ID = "system"` 常量
- **风险**：Worktree 1/2/3 都加 `Depends(get_current_user)`，依赖来源不一致
  - **缓解**：Worktree 2 创建 `src/api/dependencies.py`，Worktree 1/3 都从此 import

---

## 7. 当前会话执行步骤

1. ✅ 写计划（本文件）
2. 创建三个 git worktree（`a-share-hub-security`、`a-share-hub-watchlists`、`a-share-hub-full-binding`）
3. 在三个 worktree 中分别 dispatch 一个 team-implementer 子 agent，每个 agent 收到明确的所有权清单
4. 等三个 agent 完成后：review、merge 到 master、push、连接 AWS 拉取重启
