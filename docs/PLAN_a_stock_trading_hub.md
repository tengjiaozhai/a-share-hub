# PLAN.md — A 股自动交易中枢整合计划

## 0. 项目目标

新建一个轻量级 A 股量化交易中枢项目，不直接把以下四个项目完整合并：

- hsliuping/TradingAgents-CN
- brokermr810/QuantDinger
- ZhuLinsen/daily_stock_analysis
- TauricResearch/TradingAgents

而是抽取它们的有效设计思想，重新整合为一个可维护的新项目。

最终目标：

1. 阿里云 Linux 服务器负责：
   - A 股行情采集
   - 新闻/舆情采集
   - 技术指标计算
   - LLM / Agent 辅助分析
   - 策略信号生成
   - 模拟交易
   - 风控过滤
   - 交易意图 trade_intent 生成
   - 飞书/企业微信/邮件推送
   - 简单 Web API

2. 国内 Windows 本机负责：
   - QMT / MiniQMT / xtquant 连接
   - 本地二次风控
   - 查询资产、持仓、成交、委托
   - 后续实盘下单
   - 回写订单状态

第一阶段只做模拟盘，不允许真实下单。

---

## 1. 明确约束

### 1.1 服务器约束

目标部署环境是阿里云轻量服务器：

- 2 核 CPU
- 2GB 内存
- 40GB 磁盘
- Linux
- 可使用 Python / FastAPI / SQLite
- 不建议完整部署 MongoDB + Redis + PostgreSQL + Vue + 多 Agent 并发

因此第一版必须轻量化。

### 1.2 法务和授权约束

不要直接复制 TradingAgents-CN 的 `app/` 和 `frontend/` 目录。

只允许：

- 借鉴目录设计
- 借鉴 A 股适配思路
- 借鉴 Prompt 思路
- 借鉴数据源降级思路
- 借鉴中文报告结构

对于 Apache/MIT 许可证代码，也要保留原项目来源说明。

### 1.3 交易安全约束

第一版禁止真实下单。

必须实现：

- paper broker 模拟交易
- trade_intent 交易意图
- local risk check 本地风控
- kill switch 熔断开关
- 所有订单和信号留痕
- 不把 LLM 输出直接当订单

云端只生成 trade_intent，不生成真实券商订单。

---

## 2. 四个项目的整合策略

### 2.1 daily_stock_analysis

保留思想：

- A 股行情采集
- 新闻/舆情采集
- 自选股分析
- 定时任务
- LLM 分析报告
- 多渠道推送
- 简单 Web 服务

不保留：

- GitHub Actions 运行逻辑
- 复杂 WebUI
- 桌面客户端
- 美股/港股非必要模块
- 过重的报告样式

本项目对应模块：

- `src/data/`
- `src/news/`
- `src/scheduler/`
- `src/notify/`
- `src/reports/`

### 2.2 TradingAgents

保留思想：

- Technical Analyst
- News Analyst
- Fundamentals Analyst
- Bull Researcher
- Bear Researcher
- Trader Agent
- Risk Manager
- Portfolio Manager
- 结构化输出

不保留：

- 原项目完整 CLI
- 美股 StockTwits / Reddit 依赖
- 复杂 checkpoint
- 过深 debate rounds
- 本地 Ollama 运行

本项目对应模块：

- `src/agents/`
- `src/agents/prompts/`
- `src/decision/`

### 2.3 TradingAgents-CN

保留思想：

- 中文 Prompt
- A 股代码识别
- A 股行情数据适配
- AKShare / Tushare / Baostock 降级链
- 中文报告结构
- 多模型 Provider 配置方式

不保留：

- `app/`
- `frontend/`
- 用户系统
- 权限系统
- 角色管理
- MongoDB + Redis 完整架构
- 商业化模块

本项目对应模块：

- `src/data/providers/`
- `src/agents/prompts_zh/`
- `src/config/llm.py`

### 2.4 QuantDinger

保留思想：

- IndicatorStrategy
- ScriptStrategy
- Strategy -> Backtest -> Execute -> Monitor 闭环
- 策略接口标准化
- 回测指标
- 订单对象
- 持仓对象
- 交易监控思想

不保留：

- crypto 交易所连接
- IBKR
- MT5
- Alpaca
- SaaS
- USDT billing
- 多用户计费
- 复杂前端

本项目对应模块：

- `src/strategy/`
- `src/backtest/`
- `src/execution/`
- `src/monitor/`

---

## 3. 新项目名称和技术栈

项目名：

```text
a-stock-trading-hub
```

技术栈：

```text
Python 3.11+
FastAPI
SQLite
SQLAlchemy / SQLModel
Pydantic v2
APScheduler
Pandas
NumPy
AkShare
httpx
pytest
uvicorn
python-dotenv
```

第一版暂不使用：

```text
MongoDB
Redis
Vue
Celery
Kafka
Ollama
本地大模型
真实券商下单
```

---

## 4. 目标目录结构

请按以下结构创建项目：

```text
a-stock-trading-hub/
├── README.md
├── PLAN.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── scripts/
│   ├── run_dev.sh
│   ├── run_analysis.sh
│   ├── run_paper_trade.sh
│   └── init_db.py
├── src/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── enums.py
│   │   └── time_utils.py
│   │
│   ├── storage/
│   │   ├── db.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── data/
│   │   ├── market_data_service.py
│   │   ├── stock_pool_service.py
│   │   └── providers/
│   │       ├── base.py
│   │       ├── akshare_provider.py
│   │       ├── mock_provider.py
│   │       └── provider_chain.py
│   │
│   ├── news/
│   │   ├── news_service.py
│   │   └── mock_news_provider.py
│   │
│   ├── indicators/
│   │   ├── technical_indicators.py
│   │   └── scoring.py
│   │
│   ├── agents/
│   │   ├── llm_client.py
│   │   ├── agent_runner.py
│   │   ├── schemas.py
│   │   └── prompts/
│   │       ├── technical_analyst.md
│   │       ├── news_analyst.md
│   │       ├── bull_researcher.md
│   │       ├── bear_researcher.md
│   │       ├── trader.md
│   │       ├── risk_manager.md
│   │       └── portfolio_manager.md
│   │
│   ├── strategy/
│   │   ├── base.py
│   │   ├── ma_breakout_strategy.py
│   │   ├── rsi_reversal_strategy.py
│   │   └── signal_fusion.py
│   │
│   ├── risk/
│   │   ├── pre_trade_risk.py
│   │   ├── position_risk.py
│   │   ├── stop_loss.py
│   │   └── kill_switch.py
│   │
│   ├── execution/
│   │   ├── broker_base.py
│   │   ├── paper_broker.py
│   │   ├── trade_intent_service.py
│   │   └── schemas.py
│   │
│   ├── backtest/
│   │   ├── engine.py
│   │   ├── metrics.py
│   │   └── report.py
│   │
│   ├── notify/
│   │   ├── base.py
│   │   ├── console.py
│   │   ├── feishu.py
│   │   └── wechat.py
│   │
│   ├── scheduler/
│   │   └── jobs.py
│   │
│   └── api/
│       ├── routes_health.py
│       ├── routes_stocks.py
│       ├── routes_signals.py
│       ├── routes_trade_intents.py
│       └── routes_paper_orders.py
│
├── windows_agent/
│   ├── README.md
│   ├── qmt_executor_stub.py
│   ├── xtquant_adapter_stub.py
│   ├── local_risk_check.py
│   ├── pull_trade_intents.py
│   └── heartbeat.py
│
└── tests/
    ├── test_signal_fusion.py
    ├── test_risk.py
    ├── test_paper_broker.py
    └── test_trade_intent.py
```

---

## 5. 数据模型设计

请实现以下核心表。

### 5.1 stock_pool

字段：

```text
id
symbol
name
market
enabled
group_name
created_at
updated_at
```

示例：

```text
600519.SH
000001.SZ
300750.SZ
```

### 5.2 market_bar

字段：

```text
id
symbol
trade_date
open
high
low
close
volume
amount
created_at
```

### 5.3 analysis_signal

字段：

```text
id
symbol
trade_date
strategy_name
technical_score
news_score
agent_score
risk_score
final_score
action
confidence
reason
raw_payload_json
created_at
```

action 枚举：

```text
BUY
SELL
HOLD
WATCH
```

### 5.4 trade_intent

字段：

```text
id
symbol
action
target_value
target_quantity
max_price
min_price
confidence
risk_level
source_signal_id
status
reason
expire_at
created_at
updated_at
```

status 枚举：

```text
PENDING
APPROVED
REJECTED
EXPIRED
PULLED_BY_WINDOWS
EXECUTED_PAPER
EXECUTED_LIVE
FAILED
CANCELLED
```

### 5.5 paper_order

字段：

```text
id
trade_intent_id
symbol
side
price
quantity
amount
status
filled_at
created_at
```

### 5.6 paper_position

字段：

```text
id
symbol
quantity
avg_cost
market_value
unrealized_pnl
realized_pnl
updated_at
```

### 5.7 risk_event

字段：

```text
id
level
event_type
symbol
message
payload_json
created_at
```

---

## 6. 核心流程设计

### 6.1 每日分析流程

实现命令：

```bash
python -m src.main analyze --stocks 600519.SH,000001.SZ
```

流程：

```text
读取股票池
↓
拉取最近 120 个交易日 K 线
↓
计算 MA5 / MA10 / MA20 / MA60 / RSI / MACD / 成交量变化
↓
拉取相关新闻，第一版可以用 mock news
↓
技术策略生成初步信号
↓
Agent 生成结构化分析
↓
signal_fusion 合成最终评分
↓
risk 模块过滤
↓
生成 analysis_signal
↓
若满足条件，生成 trade_intent
↓
推送摘要
```

### 6.2 模拟交易流程

实现命令：

```bash
python -m src.main paper-trade
```

流程：

```text
读取 PENDING trade_intent
↓
检查是否过期
↓
检查风控
↓
按最新 close 模拟成交
↓
生成 paper_order
↓
更新 paper_position
↓
更新 trade_intent.status = EXECUTED_PAPER
```

### 6.3 Windows 执行网关流程

第一版只做 stub，不真实下单。

实现命令：

```bash
python windows_agent/pull_trade_intents.py
```

流程：

```text
访问云端 API /trade-intents/pending
↓
拉取待执行交易意图
↓
本地风控检查
↓
打印将要执行的动作
↓
第一版不调用真实 xtquant 下单
↓
回写状态为 PULLED_BY_WINDOWS 或 REJECTED
```

---

## 7. 策略规则

### 7.1 MA 突破策略

文件：

```text
src/strategy/ma_breakout_strategy.py
```

买入候选条件：

```text
close > MA20
MA5 > MA10
MA10 > MA20
volume > 最近 20 日平均成交量 * 1.2
RSI 在 45 到 75 之间
```

卖出候选条件：

```text
close < MA20
或 MA5 < MA10
或 RSI > 85
```

### 7.2 RSI 反转策略

文件：

```text
src/strategy/rsi_reversal_strategy.py
```

买入候选：

```text
RSI < 35
且 close 站回 MA5
```

卖出候选：

```text
RSI > 80
或 close 跌破 MA10
```

### 7.3 信号融合

文件：

```text
src/strategy/signal_fusion.py
```

评分规则：

```text
final_score =
technical_score * 0.50
+ agent_score * 0.25
+ news_score * 0.10
+ risk_score * 0.15
```

动作规则：

```text
final_score >= 75 -> BUY
60 <= final_score < 75 -> WATCH
40 <= final_score < 60 -> HOLD
final_score < 40 -> SELL
```

注意：

```text
LLM 不能直接决定 BUY/SELL
LLM 只能参与 agent_score
风控可以一票否决
```

---

## 8. 风控规则

实现：

```text
src/risk/pre_trade_risk.py
src/risk/position_risk.py
src/risk/kill_switch.py
```

第一版规则：

```text
单票最大目标仓位 <= 总资产 10%
单日最大买入金额 <= 总资产 20%
单日最多生成 5 条 BUY trade_intent
ST 股票默认禁止
退市整理股票禁止
上市未满 60 个交易日禁止
涨停不追
跌停不主动卖
final_score < 75 不允许生成 BUY trade_intent
confidence < 70 不允许生成 BUY trade_intent
kill_switch = true 时禁止所有交易意图执行
```

需要提供 `.env` 配置：

```env
ENABLE_LIVE_TRADING=false
ENABLE_PAPER_TRADING=true
KILL_SWITCH=false
MAX_SINGLE_POSITION_RATIO=0.10
MAX_DAILY_BUY_RATIO=0.20
MIN_BUY_SCORE=75
MIN_BUY_CONFIDENCE=70
```

---

## 9. Agent 结构化输出

LLM 输出必须强制 JSON。

schema：

```json
{
  "symbol": "600519.SH",
  "action": "BUY|SELL|HOLD|WATCH",
  "confidence": 0,
  "agent_score": 0,
  "risk_level": "low|medium|high",
  "bull_points": [],
  "bear_points": [],
  "risk_points": [],
  "suggested_position_ratio": 0.0,
  "reason": ""
}
```

如果 LLM 输出无法解析：

```text
agent_score = 50
action = HOLD
confidence = 0
risk_level = high
reason = "LLM output parse failed"
```

不要因为 LLM 异常导致程序中断。

---

## 10. API 设计

使用 FastAPI 实现。

### 10.1 健康检查

```http
GET /health
```

返回：

```json
{
  "status": "ok"
}
```

### 10.2 股票池

```http
GET /stocks
POST /stocks
PATCH /stocks/{symbol}
```

### 10.3 信号

```http
GET /signals
GET /signals/{id}
```

### 10.4 交易意图

```http
GET /trade-intents/pending
POST /trade-intents/{id}/approve
POST /trade-intents/{id}/reject
POST /trade-intents/{id}/mark-pulled
```

第一版不做复杂权限，但需要一个简单 API token。

请求头：

```http
Authorization: Bearer <API_TOKEN>
```

### 10.5 模拟订单

```http
GET /paper-orders
GET /paper-positions
```

---

## 11. 命令行入口

实现以下命令：

```bash
python -m src.main init-db
python -m src.main add-stock 600519.SH 贵州茅台
python -m src.main analyze --stocks 600519.SH
python -m src.main analyze-all
python -m src.main paper-trade
python -m src.main serve
python -m src.main scheduler
```

---

## 12. .env.example

生成以下配置：

```env
APP_ENV=dev
DATABASE_URL=sqlite:///./data/a_stock_hub.db
API_TOKEN=change_me

OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=

ENABLE_LIVE_TRADING=false
ENABLE_PAPER_TRADING=true
KILL_SWITCH=false

MAX_SINGLE_POSITION_RATIO=0.10
MAX_DAILY_BUY_RATIO=0.20
MIN_BUY_SCORE=75
MIN_BUY_CONFIDENCE=70

FEISHU_WEBHOOK=
WECHAT_WEBHOOK=
```

---

## 13. README 要求

README 必须包括：

1. 项目定位
2. 四个参考项目分别借鉴了什么
3. 为什么不直接合并四个项目
4. 本项目第一版为什么只做模拟盘
5. 安装方式
6. 配置方式
7. 初始化数据库
8. 添加自选股
9. 执行分析
10. 执行模拟交易
11. 启动 API
12. Windows Agent 使用方式
13. 风控说明
14. 免责声明

---

## 14. 测试要求

至少实现以下测试：

```text
test_signal_fusion.py
- final_score 计算正确
- BUY/WATCH/HOLD/SELL 判断正确

test_risk.py
- 分数不够不能买
- kill switch 开启时不能交易
- 单票仓位超限不能交易

test_paper_broker.py
- PENDING trade_intent 可以生成 paper_order
- paper_position 可以更新
- 过期 trade_intent 不执行

test_trade_intent.py
- trade_intent 创建正确
- status 流转正确
```

运行：

```bash
pytest -q
```

必须全部通过。

---

## 15. 分阶段执行计划

### Phase 1：项目骨架

目标：

```text
建立目录结构
配置 pyproject.toml
配置 .env.example
实现 config/logger/enums
实现 SQLite 数据库初始化
```

验收：

```bash
python -m src.main init-db
pytest -q
```

### Phase 2：股票池和行情数据

目标：

```text
实现 stock_pool
实现 mock_provider
实现 akshare_provider
实现 provider_chain
实现 market_data_service
```

验收：

```bash
python -m src.main add-stock 600519.SH 贵州茅台
python -m src.main analyze --stocks 600519.SH
```

即使 AkShare 失败，也要能 fallback 到 mock_provider。

### Phase 3：技术指标和策略

目标：

```text
实现 MA / RSI / MACD
实现 ma_breakout_strategy
实现 rsi_reversal_strategy
实现 signal_fusion
```

验收：

```bash
pytest tests/test_signal_fusion.py -q
```

### Phase 4：Agent 分析

目标：

```text
实现 llm_client
实现 agent_runner
实现 prompts
实现 JSON 结构化输出解析
实现 LLM 异常降级
```

验收：

```bash
python -m src.main analyze --stocks 600519.SH
```

没有 API Key 时，系统不能崩溃，应自动使用 mock agent 输出。

### Phase 5：风控和交易意图

目标：

```text
实现 pre_trade_risk
实现 position_risk
实现 kill_switch
实现 trade_intent_service
```

验收：

```bash
pytest tests/test_risk.py tests/test_trade_intent.py -q
```

### Phase 6：模拟交易

目标：

```text
实现 broker_base
实现 paper_broker
实现 paper_order
实现 paper_position
```

验收：

```bash
python -m src.main paper-trade
pytest tests/test_paper_broker.py -q
```

### Phase 7：FastAPI

目标：

```text
实现 /health
实现 /stocks
实现 /signals
实现 /trade-intents/pending
实现 /paper-orders
实现 /paper-positions
实现 API_TOKEN 鉴权
```

验收：

```bash
python -m src.main serve
curl http://127.0.0.1:8000/health
```

### Phase 8：Windows Agent Stub

目标：

```text
实现 windows_agent/pull_trade_intents.py
实现 local_risk_check.py
实现 qmt_executor_stub.py
```

注意：

```text
不要真实调用 xtquant 下单
只打印模拟执行
```

验收：

```bash
python windows_agent/pull_trade_intents.py
```

### Phase 9：定时任务和通知

目标：

```text
实现 scheduler/jobs.py
实现 console notify
实现 feishu notify
实现 wechat notify
```

验收：

```bash
python -m src.main scheduler
```

---

## 16. 实现优先级

优先实现：

```text
数据模型
行情数据
技术指标
策略信号
风控
模拟交易
API
Windows stub
```

暂缓实现：

```text
真实下单
复杂 WebUI
多用户系统
复杂回测图表
Redis
MongoDB
PostgreSQL
Docker Compose
本地大模型
```

---

## 17. 代码风格要求

1. 所有核心函数要有类型注解
2. 所有外部 API 调用要有异常处理
3. 所有 LLM 输出要做 JSON parse 保护
4. 不允许在代码里硬编码 API Key
5. 不允许提交 `.env`
6. 不允许真实下单
7. 所有交易动作必须先经过 risk 模块
8. 所有订单状态流转必须写入数据库
9. 所有策略输出必须可解释
10. 测试必须通过

---

## 18. 第一版完成标准

第一版完成后，应该能够做到：

```bash
python -m src.main init-db
python -m src.main add-stock 600519.SH 贵州茅台
python -m src.main analyze --stocks 600519.SH
python -m src.main paper-trade
python -m src.main serve
python windows_agent/pull_trade_intents.py
pytest -q
```

并且满足：

```text
1. 能生成 analysis_signal
2. 能生成 trade_intent
3. 能执行 paper_order
4. 能更新 paper_position
5. 能通过 API 查询结果
6. 能通过 Windows Agent 拉取交易意图
7. 不会真实下单
8. 风控可以阻断交易
9. kill switch 可以阻断全部交易
10. 没有 LLM API Key 时也能跑通 mock 流程
```

---

## 19. Codex 执行方式

请按 Phase 1 到 Phase 9 顺序执行。

每完成一个 Phase：

1. 运行相关测试
2. 修复报错
3. 更新 README
4. 输出本阶段完成内容
5. 输出下一阶段计划

不要一次性实现真实下单。

不要复制四个项目的完整代码。

优先保证最小闭环跑通。

---

## 20. 给 Codex 的执行提示

请严格按 PLAN.md 执行，先完成 Phase 1-6，暂时不要做真实下单和复杂 WebUI。目标是先跑通：

```text
行情数据 → 技术指标 → Agent 分析 → 风控 → trade_intent → paper_order
```

的最小闭环。
