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
- **运行一轮模拟交易**: 执行完整的决策→目标仓位→执行→对账流程（手动沙盒）
- **快速回测**: 测试策略在历史数据上的表现
- **区间表现**: 今日收益 / 月度收益 / 最大回撤 / 累计净值曲线（来自 auto 账户）
- **自动交易状态**: 今日状态 / 最后运行时间 / 下次运行时间（A 股 9:15、美股 21:15 北京时间）

### 中间绩效面板

#### 自动运行状态
显示自动交易系统的运行状态：
- **今日状态**: `pending`（待运行）/ `success`（成功）/ `failed`（失败）
- **最后运行**: 最近一次自动运行的时间
- **下次运行**: 下一次自动运行的时间（A 股 09:15、美股 21:15 北京时间）

#### 净值曲线
展示 auto 账户的累计净值走势图：
- 数据来源：`paper_nav_daily` 表（累计曲线唯一来源）
- 显示范围：最近 30 个交易日
- 用途：直观查看策略的整体表现趋势

#### 区间表现对比
支持多个时间窗口的业绩对比：
- **7天**: 最近 7 个交易日的表现
- **30天**: 最近 30 个交易日的表现
- **90天**: 最近 90 个交易日的表现
- **YTD**: 年初至今的表现
- 点击切换不同时间窗口，查看对应区间的数据

#### 最近运行记录
显示最近的交易运行记录，支持两种模式切换：
- **自动**: 显示自动调度器运行的记录（按时间倒序）
- **手动**: 显示手动点击「运行一轮模拟交易」的记录
- 每条记录显示：运行阶段（决策/目标仓位/执行/对账）、状态、时间、详细信息

### 右侧栏：区间表现与风控

#### 区间表现（KPI 卡片）
- **今日收益**: 当日的收益率（百分比）
- **月度收益**: 当月的收益率（百分比）
- **最大回撤**: 历史最大回撤幅度（百分比）
- 数据来源：auto 账户的 `paper_nav_daily` 表

#### 风控状态
实时监控风控指标：
- **当日累计盈亏**: 当日的盈亏金额（CNY）
- **持仓集中度**: 最大持仓占总资金的比例
- **活跃目标仓位**: 当前有效的目标仓位数量
- **未完成订单**: 待执行或执行中的订单数量

#### 执行模式
- **完整链路**: 决策 → 目标仓位 → 执行 → 对账（完整流程）
- **仅决策**: 只生成交易建议，不执行订单（用于验证策略）

### A股/美股工作台
- **实时行情**: 查看股票实时价格和涨跌幅
- **自选管理**: 添加/删除自选股票
- **搜索功能**: 搜索全市场股票
- **K线图**: 查看股票历史走势
- **基本面**: 查看股票财务数据

### 行情列表
- **搜索模式**: 搜索全市场，点击「+ 添加」加入自选
- **自选模式**: 查看自选股票行情，点击「删除」移除

### 自动日频模拟交易
- **调度器**: APScheduler 内置于 FastAPI 进程，按市场自动日频运行
  - A 股：周一至周五 09:15（北京时间）
  - 美股：周一至周五 21:15（北京时间）
- **账本隔离**: auto 账户与 manual（手动沙盒）账户完全隔离，互不影响
- **业绩权威**: `paper_nav_daily` 为累计曲线唯一来源
- **启动补算**: 启动时若 auto 账户无近 30 个交易日净值，自动触发受控 backfill

### 每日模拟交易结果报告

#### 数据存储
每次模拟交易运行结果保存在以下表中：

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `paper_runs` | 运行记录 | `run_id`, `trade_date`, `run_source` (auto/manual/backfill), `status` (running/success/failed) |
| `paper_fills` | 成交明细 | `fill_id`, `run_id`, `symbol`, `action` (BUY/SELL), `quantity`, `price` |
| `paper_positions` | 当前持仓 | `position_id`, `symbol`, `quantity`, `avg_cost` |
| `paper_nav_daily` | 每日净值 | `nav_id`, `trade_date`, `nav`, `cash`, `positions_value` |

#### 查看运行结果

**仪表盘查看：**
1. **最近运行记录**（中间面板底部）：
   - 点击「自动」标签查看自动运行记录
   - 点击「手动」标签查看手动运行记录
   - 每条记录显示：市场、状态、时间、错误信息（如有）

2. **净值曲线**（中间面板）：
   - 展示 `paper_nav_daily` 表中的累计净值走势
   - 数据来源：auto 账户的每日净值快照

3. **区间表现**（右侧面板）：
   - 今日收益、月度收益、最大回撤
   - 支持 7天/30天/90天/YTD 时间窗口切换

**API 查看：**
```bash
# 获取运行历史
curl "http://localhost:8000/api/v1/dashboard/history?market=a&source=all&limit=20"

# 返回结构
{
  "auto_runs": [...],      // 自动运行记录
  "manual_runs": [...],    // 手动运行记录
  "fills": [...]           // 净值历史
}
```

#### 一日一保存机制

**自动运行（auto）：**
- 每个交易日自动运行一次
- 运行时间：A股 09:15 / 美股 21:15（北京时间）
- 保存内容：
  1. `paper_runs`：插入一条 `run_source="auto"` 的记录
  2. `paper_fills`：插入当日所有成交记录
  3. `paper_positions`：更新当前持仓
  4. `paper_nav_daily`：插入当日净值快照（nav, cash, positions_value）

**手动运行（manual）：**
- 用户点击「运行一轮模拟交易」触发
- 保存内容与自动运行相同，但 `run_source="manual"`

**净值计算公式：**
```
nav = cash + positions_value
positions_value = Σ(quantity × current_price)  // 按最新价计算
```

#### 数据查看示例

```sql
-- 查看最近 7 天的自动运行记录
SELECT run_id, trade_date, status, created_at 
FROM paper_runs 
WHERE market = 'a' AND run_source = 'auto'
ORDER BY trade_date DESC 
LIMIT 7;

-- 查看某日的成交明细
SELECT symbol, action, quantity, price, notional
FROM paper_fills 
WHERE run_id = 'run-xxx';

-- 查看净值走势
SELECT trade_date, nav, cash, positions_value
FROM paper_nav_daily
WHERE account_id = 'acct-a-auto'
ORDER BY trade_date DESC
LIMIT 30;
```

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

服务启动后会自动：
- 注册并启动日频调度器（A 股 9:15 / 美股 21:15 北京时间）
- 检查 auto 账户是否需要 backfill（首次启动会自动补近 30 个交易日）

## 运行时存储

运行时控制平面使用 PostgreSQL（通过 `DATABASE_URL`）。

**真实运行节点推荐配置**：`DATABASE_URL` 指向本机 loopback，由 SSH 隧道转发到 AWS PostgreSQL：

```
DATABASE_URL=postgresql+psycopg://douya:change_me@127.0.0.1:15432/douya
```

- AWS PostgreSQL 是唯一权威库
- SSH 隧道由 systemd 托管，应用进程不感知 AWS 主机地址
- 验证命令：`/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py`
- Readiness 接口：`GET /health/ready`（数据库不可达时返回 `503`）
- 详细运维见 `docs/runbooks/aws-pg-ssh-tunnel.md`

Redis 是可选的，必须保持禁用直到负载门控运行手册另有说明。

## 引导

1. 从 `.env.example` 配置 `.env`。
2. **真实运行节点**：确认 `DATABASE_URL` 指向 `127.0.0.1:<port>`，启动 SSH 隧道（见 runbook）。
3. 验证数据库连通性：`/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py`
4. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head`。
   若数据库中只有 `alembic_version` 或没有业务表，应用在首次初始化 `RuntimeStore` 时会自动补齐运行时表。
5. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m pytest -q`。
6. 运行 `bash scripts/run_shadow_cycle.sh`。

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
- `POST /api/v1/dashboard/runs` - 启动一轮模拟交易（流式，202 Accepted）
- `GET /api/v1/dashboard/runs/{run_context_id}/events` - SSE 事件流（stage 推进 + reconcile 快照）
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

详细的新手 SOP 请查看 [docs/sop.md](docs/sop.md)
