# A股自动交易系统

## 概述

基于多智能体LLM决策的A股自动交易系统，包含数据采集、特征工程、决策引擎、风险控制和执行网关。

## 架构

- **Linux研究节点**: 市场数据、LLM决策、回测、组合管理
- **Windows执行节点**: QMT/MiniQMT实盘执行

## 快速开始

1. 安装Python 3.11环境
2. 安装依赖：`pip install -e .`
3. 配置 `.env` 文件
4. 运行测试：`pytest tests/`

## 影子模式

系统使用fail-closed影子模式脚本进行安全测试：

```bash
# 运行影子周期
./scripts/run_shadow_cycle.sh

# 运行对账
./scripts/run_reconcile.sh
```

所有脚本都遵循fail-closed原则：任何步骤失败都会导致整个脚本退出，确保问题不会被忽略。

## 后台服务

启动后端 API 服务：

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

服务默认监听 `0.0.0.0:8000`。

## 模块说明

- `src/core/`: 核心配置和工具
- `src/data/`: 数据提供者
- `src/indicators/`: 技术指标
- `src/strategy/`: 策略逻辑
- `src/decision/`: 决策引擎
- `src/agents/`: LLM代理
- `src/portfolio/`: 组合管理
- `src/risk/`: 风险控制
- `src/execution/`: 执行引擎
- `windows_agent/`: Windows执行节点

## 运行时存储

运行时控制平面使用 PostgreSQL（通过 `DATABASE_URL`）。
Redis 是可选的，必须保持禁用直到负载门控运行手册另有说明。

## 引导

1. 从 `.env.example` 配置 `.env`。
2. 通过 `DATABASE_URL` 验证 PostgreSQL 连接。
3. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head`。
   若数据库中只有 `alembic_version` 或没有业务表，应用在首次初始化 `RuntimeStore` 时会自动补齐运行时表。
4. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m pytest -q`。
5. 运行 `bash scripts/run_shadow_cycle.sh`。

## Alpha 代币化证券操作台

- 公开资产数据通过 `/api/v1/alpha/assets` 提供
- 建议单通过 `/api/v1/alpha/tickets` 创建与查看
- 人工执行结果通过 `/api/v1/alpha/tickets/{ticket_id}/fills` 回填
- 当前版本不支持自动下单
- 研究扫描与候选转建议单流程见 `docs/runbooks/alpha-research-and-ops-ui.md`

## Alpha 账本与对账

- 组合快照通过 `/api/v1/alpha/portfolio` 查看
- 对账通过 `/api/v1/alpha/reconciliation/run` 触发
- Dashboard 异常区展示对账差异
- 详细操作流程见 `docs/runbooks/alpha-ledger-and-reconciliation.md`

## Alpha 执行能力门控

Phase 4 引入了安全门控机制，控制 API 下单能力的启用：

- 能力状态通过 `/api/v1/alpha/capabilities` 查询
- 订单预览通过 `/api/v1/alpha/orders/preview` 验证
- 订单提交通过 `/api/v1/alpha/orders/submit` 执行（需启用 API 模式）
- 默认模式为 `manual`，需要人工确认
- 启用 API 模式前必须通过 preview 验证
- 详细操作流程见 `docs/runbooks/alpha-execution-capability-gate.md`
