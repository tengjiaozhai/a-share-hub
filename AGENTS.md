# AGENTS.md

## Python 环境

所有 Python 命令必须使用 Conda 环境的绝对路径：
```
/opt/anaconda3/envs/py311/bin/python3
```
不要用 `python` 或 `python3`。

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 测试（默认使用 SQLite，不需要 PG）
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q

# 单个测试
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_xxx.py::test_func -v

# lint
ruff check src/ tests/

# 类型检查
mypy src/

# 数据库迁移
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head

# 启动服务
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

## 测试

- 测试默认使用 SQLite（`conftest.py` 中 `tmp_path`），不需要运行 PostgreSQL
- 如需测试 PG 特性，设置 `TEST_DATABASE_URL` 环境变量
- `asyncio_mode = "auto"`，pytest-asyncio 不需要 `@pytest.mark.asyncio` 标记

## 架构要点

- **入口**: `src/main.py` 同时是 CLI 入口和 ASGI app（`uvicorn src.main:app`）
- **CLI 子命令**: `decide`, `shadow-execute`, `reconcile`, `backtest`, `evaluate-shadow`, `halt`, `serve`
- **双节点**: Linux 做研究/决策，Windows（`windows_agent/`）做 QMT 实盘执行
- **模拟账本**: `paper_ledger/` 隔离 auto/manual 账户，`paper_nav_daily` 是净值唯一来源
- **调度器**: APScheduler 内嵌 FastAPI 进程，A股 09:15 / 美股 21:15（北京时间）
- **影子模式**: 所有脚本 fail-closed，失败即退出（`set -euo pipefail`）

## 模块边界

| 目录 | 职责 |
|------|------|
| `src/core/` | 配置、Settings |
| `src/data/` | 行情数据（A股 Akshare/Tushare，美股 Yahoo） |
| `src/decision/` | LLM 决策引擎 |
| `src/portfolio/` | 目标仓位计算 |
| `src/execution/` | 模拟执行 |
| `src/risk/` | 风控门（Kill Switch 等） |
| `src/paper_ledger/` | 模拟账本（auto/manual 隔离） |
| `src/alpha/` | Alpha 代币化证券 |
| `src/scheduler/` | APScheduler 日频调度 |
| `src/storage/` | SQLAlchemy ORM + RuntimeStore |
| `windows_agent/` | Windows QMT 执行节点（独立运行） |

## 配置

- 从 `.env.example` 复制 `.env`，必须配置 `DATABASE_URL` 和 `LLM_API_KEY`
- Redis 默认**禁用**（`REDIS_ENABLED=false`），除非负载门控 runbook 另有要求
- Kill Switch 通过 API 或 CLI `halt` 命令控制

## 代码风格

- line-length 120
- ruff select: `E, F, W, I, N, UP, B, A, C4, SIM`
- mypy strict 模式

## 项目索引

### 入口与服务

| 文件 | 职责 |
|------|------|
| `src/main.py` | CLI 入口 + FastAPI app 构建 + ASGI 导出（`app = build_app()`） |
| `src/core/config.py` | Pydantic Settings，从 `.env` 加载所有配置 |
| `src/core/enums.py` | 全局枚举（市场类型、订单状态等） |
| `src/core/market_clock.py` | 交易日历与市场时间判断 |
| `src/core/market_rules.py` | 市场规则（整手、T+1 等） |

### API 层 — `src/api/`

| 文件 | 路由前缀 | 职责 |
|------|----------|------|
| `routes_health.py` | `/health` | 健康检查 |
| `routes_dashboard.py` | `/api/v1/dashboard` | 工作台（运行/回测/配置） |
| `routes_market.py` | `/api/v1/market` | A 股行情（搜索/实时/批量） |
| `routes_alpha.py` | `/api/v1/alpha` | Alpha 证券操作台（建议单/组合/对账/能力门控） |
| `routes_kill_switch.py` | `/api/v1/kill-switch` | Kill Switch 激活/解除 |
| `routes_decision_runs.py` | `/api/v1/decision-runs` | 决策运行记录查询 |
| `routes_execution_plans.py` | `/api/v1/execution-plans` | 执行计划 CRUD |
| `routes_broker_events.py` | `/api/v1/broker-events` | 券商事件回调 |
| `routes_portfolio_targets.py` | `/api/v1/portfolio-targets` | 目标仓位管理 |
| `routes_reconciliation.py` | `/api/v1/reconciliation` | 对账触发 |
| `routes_crypto.py` | `/api/v1/crypto` | 加密货币行情/交易 |
| `dashboard_contracts.py` | — | 仪表盘前后端数据契约 |
| `dashboard_page/render.py` | `/dashboard` | 服务端渲染 HTML 仪表盘 |
| `dashboard_page/shell.html` | — | 仪表盘 HTML 外壳 |
| `dashboard_page/partials/` | — | 局部 HTML（status_bar / view_dashboard / view_market / view_alpha / view_us_stock） |
| `dashboard_page/scripts/` | — | 前端 JS（bootstrap / dashboard / market / alpha / us_stock / theme / utils） |
| `dashboard_page/styles/dashboard.css` | — | 仪表盘样式 |

### 数据层 — `src/data/`

| 文件 | 职责 |
|------|------|
| `providers/base.py` | `DataProvider` 抽象基类 + `MarketSnapshot` 模型 |
| `providers/akshare_provider.py` | A 股 Akshare 数据源实现 |
| `providers/akshare_catalog.py` | Akshare 股票目录缓存 |
| `providers/akshare_snapshot_cache.py` | Akshare 快照缓存层 |
| `providers/akshare_errors.py` | Akshare 异常分类 |
| `providers/tushare_provider.py` | A 股 Tushare 备用数据源 |
| `providers/mock_provider.py` | 模拟数据源（测试用） |
| `providers/provider_chain.py` | 数据源链式 fallback（auto 模式） |
| `market_snapshot_service.py` | 行情快照聚合服务 |

### A 股自选 — `src/a_stock/`

| 文件 | 职责 |
|------|------|
| `routes.py` | A 股自选 FastAPI 路由（`/api/v1/a-stock/watchlist`） |
| `watchlist.py` | 自选 CRUD 业务逻辑 |
| `models.py` | A 股自选 Pydantic 模型 |

### 美股自选 — `src/us_stock/`

| 文件 | 职责 |
|------|------|
| `routes.py` | 美股自选 FastAPI 路由（`/api/v1/us-stock/watchlist`） |
| `watchlist.py` | 自选 CRUD 业务逻辑 |
| `yahoo_provider.py` | Yahoo Finance 数据源 |
| `binance_asset.py` | Binance 资产数据桥接 |
| `cache.py` | 行情/K 线/基本面缓存 |
| `models.py` | 美股自选 Pydantic 模型 |

### 加密货币 — `src/crypto/`

| 文件 | 职责 |
|------|------|
| `core/enums.py` | 加密货币枚举（交易对、订单类型） |
| `data/binance_provider.py` | Binance REST API 数据源 |
| `data/websocket_manager.py` | Binance WebSocket 实时推送 |
| `data/data_cache.py` | 加密货币数据缓存 |
| `execution/binance_client.py` | Binance 下单客户端 |
| `execution/order_manager.py` | 订单生命周期管理 |
| `risk/risk_manager.py` | 加密货币风控 |
| `strategy/indicators.py` | 加密货币技术指标 |

### 决策引擎 — `src/agents/` + `src/decision/` + `src/strategy/`

| 文件 | 职责 |
|------|------|
| `agents/llm_client.py` | LLM 调用封装（DeepSeek / mock） |
| `agents/prompts/system.md` | 系统 Prompt 模板 |
| `agents/prompts/trader.md` | 交易员角色 Prompt |
| `agents/schemas.py` | LLM 输出 JSON Schema |
| `decision/decision_runner.py` | 决策执行编排（构建记录 → 持久化） |
| `decision/input_builder.py` | 构建决策输入快照（行情+特征+上下文） |
| `strategy/signal_engine.py` | 多因子信号评分引擎 |
| `strategy/stock_scanner.py` | 全市场扫描 |
| `strategy/candidate_filter.py` | 候选股票筛选 |
| `strategy/strategy_config.py` | 策略参数配置 |

### 技术指标 — `src/indicators/`

| 文件 | 职责 |
|------|------|
| `technical_indicators.py` | MA / 动量 / 波动率 / 量比等计算 |

### 组合管理 — `src/portfolio/`

| 文件 | 职责 |
|------|------|
| `target_planner.py` | 目标仓位计算（整手、集中度限制） |

### 执行引擎 — `src/execution/`

| 文件 | 职责 |
|------|------|
| `paper_execution_service.py` | 模拟执行服务 |
| `paper_broker.py` | 模拟券商（生成 fill） |
| `paper_portfolio.py` | 模拟持仓管理 |
| `execution_plan_service.py` | 执行计划生成与状态追踪 |
| `state_machine.py` | 订单状态机（READY → PARTIALLY_FILLED → FILLED 等，幂等） |
| `reconciliation.py` | 对账逻辑（持仓 vs 订单 vs fill） |

### 风控 — `src/risk/`

| 文件 | 职责 |
|------|------|
| `kill_switch.py` | Kill Switch 状态管理（PG 存储） |
| `pre_trade_risk.py` | 交易前风控门（集中度/日亏损/止损等） |

### 模拟账本 — `src/paper_ledger/`

| 文件 | 职责 |
|------|------|
| `store.py` | `PaperLedgerStore` — 账本 CRUD（`paper_runs` / `paper_fills` / `paper_positions` / `paper_nav_daily`） |
| `models.py` | 模拟账本 ORM 模型 |
| `backfill.py` | 启动时净值补算（`needs_backfill` / `backfill_recent_days`） |

### Alpha 代币化证券 — `src/alpha/`

| 文件 | 职责 |
|------|------|
| `signal_engine.py` | Alpha 信号引擎 |
| `research_service.py` | 研究扫描与候选生成 |
| `service.py` | Alpha 服务编排（建议单 → 审核 → 执行） |
| `execution_service.py` | Alpha 执行服务 |
| `execution_gateway.py` | 执行能力门控（manual / api 模式） |
| `execution_models.py` | 执行相关 Pydantic 模型 |
| `portfolio_service.py` | Alpha 组合快照服务 |
| `reconciliation.py` | Alpha 对账 |
| `ledger.py` | Alpha 账本 |
| `binance_public_client.py` | Binance 公开数据客户端 |
| `models.py` | Alpha Pydantic 模型 |

### 调度器 — `src/scheduler/`

| 文件 | 职责 |
|------|------|
| `daily_scheduler.py` | APScheduler 日频调度（A 股 09:15 / 美股 21:15 CST） |

### 评估 — `src/evaluation/`

| 文件 | 职责 |
|------|------|
| `long_run.py` | 长期 shadow 评估（1m / 3m / 1y 窗口） |

### 回测 — `src/backtest/`

| 文件 | 职责 |
|------|------|
| `engine.py` | 日频回测引擎（整手 / 费用 / 滑点） |
| `metrics.py` | 回测指标计算（收益率 / 最大回撤 / 夏普等） |

### 存储层 — `src/storage/`

| 文件 | 职责 |
|------|------|
| `models.py` | 所有 SQLAlchemy ORM 模型（17 张表） |
| `runtime_store.py` | `RuntimeStore` — 运行时数据读写（818 行，核心数据层） |
| `db.py` | 数据库引擎创建与连接池配置 |
| `dependencies.py` | FastAPI 依赖注入（`get_runtime_store`） |
| `redis_cache.py` | Redis 缓存（默认禁用） |

### Windows 执行节点 — `windows_agent/`

| 文件 | 职责 |
|------|------|
| `pull_execution_plans.py` | 从 Linux 拉取执行计划 |
| `xtquant_adapter.py` | QMT/MiniQMT 实盘下单适配 |
| `local_risk_check.py` | Windows 本地风控二次检查 |
| `heartbeat.py` | 心跳上报 |

### 影子模式脚本 — `scripts/`

| 文件 | 职责 |
|------|------|
| `run_shadow_cycle.sh` | 影子周期：decide → shadow-execute → reconcile → evaluate |
| `run_reconcile.sh` | 独立对账 |
| `init_a_share_watchlist.py` | 初始化 A 股自选 |
| `init_us_watchlist.py` | 初始化美股自选 |

### 数据库迁移 — `alembic/versions/`

| 版本 | 内容 |
|------|------|
| `000001` | 运行时存储基础表 |
| `000002` | 决策 & 执行实体 |
| `000003` | 执行订单 & 事件 |
| `000004` | Alpha 仓位快照 & 对账表 |
| `000005` | Alpha API 下单尝试表 |
| `000006` | 美股自选表 |
| `000007` | A 股自选表 |
| `000008` | 数据库 Schema 注释 |
| `000009` | `paper_nav_daily` provenance 字段 |

### 文档 — `docs/`

| 文件/目录 | 内容 |
|-----------|------|
| `runbooks/alpha-desk.md` | Alpha 操作台运维手册 |
| `runbooks/alpha-execution-capability-gate.md` | 执行能力门控操作 |
| `runbooks/alpha-ledger-and-reconciliation.md` | Alpha 账本对账 |
| `runbooks/alpha-research-and-ops-ui.md` | 研究扫描流程 |
| `runbooks/dashboard_user_guide.md` | 仪表盘使用指南 |
| `runbooks/infrastructure-load-gate.md` | 负载门控 |
| `runbooks/live-trading.md` | 实盘交易操作 |
| `runbooks/long-horizon-evaluation.md` | 长期评估 |
| `architecture.md` | 系统架构文档 |
| `sop.md` | 新手 SOP |

### 核心数据流

```
行情数据 → 技术指标 → 信号引擎 → LLM 决策 → 目标仓位 → 风控门 → 执行计划 → 模拟执行 → 对账 → 净值记录
                ↑                                                              ↓
           调度器触发                                                    paper_nav_daily
```
