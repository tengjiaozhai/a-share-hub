# A股/美股自动交易系统

## 概述

基于多智能体LLM决策的量化交易系统，支持A股和美股，包含数据采集、特征工程、决策引擎、风险控制和执行网关。

## 架构

- **Linux研究节点**: 市场数据、LLM决策、回测、组合管理
- **Windows执行节点**: QMT/MiniQMT实盘执行

## 快速开始

1. 安装Python 3.11环境
2. 安装依赖：`pip install -e .`
3. 配置 `.env` 文件
4. 运行测试：`pytest tests/`

## 启动仪表盘

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

访问 http://localhost:8000/dashboard

## 仪表盘功能

### 工作台
- **策略配置**: 设置观察列表、资金、止损等参数
- **运行一轮模拟交易**: 执行完整的决策→目标仓位→执行→对账流程
- **快速回测**: 测试策略在历史数据上的表现

### A股/美股工作台
- **实时行情**: 查看股票实时价格和涨跌幅
- **自选管理**: 添加/删除自选股票
- **搜索功能**: 搜索全市场股票
- **K线图**: 查看股票历史走势
- **基本面**: 查看股票财务数据

### 行情列表
- **搜索模式**: 搜索全市场，点击「+ 添加」加入自选
- **自选模式**: 查看自选股票行情，点击「删除」移除

## 策略说明

### 多因子选股模型

| 指标 | 含义 | 权重 |
|------|------|------|
| 20日动量 | 过去20天涨跌幅 | 30% |
| 60日动量 | 过去60天涨跌幅 | 25% |
| MA20偏离 | 价格偏离20日均线 | 20% |
| MA60偏离 | 价格偏离60日均线 | 15% |
| 量比 | 成交量vs平均成交量 | 10% |
| 波动率 | 价格波动幅度 | -10% |

### 信号规则

- 综合评分 ≥ 0.55 → **BUY**
- 综合评分 ≤ -0.20 → **SELL**
- 其他 → **HOLD**

## 模块说明

- `src/core/`: 核心配置和工具
- `src/data/`: 数据提供者（A股: Akshare, 美股: Yahoo Finance）
- `src/indicators/`: 技术指标计算
- `src/strategy/`: 策略逻辑（信号引擎、扫描器）
- `src/decision/`: 决策引擎
- `src/portfolio/`: 组合管理（目标仓位计算）
- `src/risk/`: 风险控制（交易前风控门）
- `src/execution/`: 执行引擎（模拟执行服务）
- `src/evaluation/`: 评估系统（长期shadow评估）
- `src/backtest/`: 回测引擎（支持整手、费用、滑点）
- `src/a_stock/`: A股自选管理
- `src/us_stock/`: 美股自选管理
- `windows_agent/`: Windows执行节点

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

## API 接口

### 市场数据
- `GET /api/v1/market/stocks` - A股搜索
- `GET /api/v1/market/quote` - A股实时行情
- `POST /api/v1/market/bulk` - A股批量行情

### 自选管理
- `GET /api/v1/a-stock/watchlist` - A股自选列表
- `POST /api/v1/a-stock/watchlist` - 添加A股自选
- `DELETE /api/v1/a-stock/watchlist/{symbol}` - 删除A股自选
- `GET /api/v1/us-stock/watchlist` - 美股自选列表
- `POST /api/v1/us-stock/watchlist` - 添加美股自选
- `DELETE /api/v1/us-stock/watchlist/{symbol}` - 删除美股自选

### 仪表盘
- `POST /api/v1/dashboard/run` - 运行一轮模拟交易
- `POST /api/v1/dashboard/backtest` - 运行回测
- `GET /api/v1/dashboard/workbench` - 获取工作台数据
- `GET /api/v1/dashboard/preferences` - 获取配置
- `PUT /api/v1/dashboard/preferences` - 保存配置

### 风险控制
- `POST /api/v1/kill-switch/activate` - 激活紧急停止
- `POST /api/v1/kill-switch/deactivate` - 解除紧急停止

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

## 新手指南

详细的新手交易计划请查看 [sop.md](sop.md)
