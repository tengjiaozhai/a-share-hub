# 美股行情查询模块设计文档

## 概述

在 a-share-hub 中新增独立的美股行情查询模块，基于 yfinance 获取行情/K线/基本面数据，集成币安 API 查询账户美股资产，并在 Dashboard 中新增美股 tab。

## 背景

- 现有 `routes_market.py:84-217` 通过 Stooq 提供约 30 只美股基础行情，数据有限（仅 OHLC）
- 币安已于 2026-06-01 上线 7000+ 美股直接交易，Stock Perps 已有完整 API
- 用户需要更丰富的美股数据（实时行情、K线、基本面、搜索）+ 币安账户资产查询

## 方案选择

**方案 A：yfinance + BinanceProvider 扩展（选定）**

- 新增 `src/us_stock/` 独立模块
- yfinance 获取行情/K线/基本面，Binance API 查持仓资产
- 自选列表存 PostgreSQL，支持动态增删
- Dashboard 新增美股 tab

理由：yfinance 是 Python 生态中最成熟的美股数据库，一个库覆盖所有数据需求；独立模块与现有 `crypto/` 结构一致。

## 模块结构

```
src/us_stock/
├── __init__.py
├── models.py              # Pydantic 模型
├── yahoo_provider.py      # yfinance 封装
├── binance_asset.py       # 币安账户美股资产查询
├── watchlist.py           # 自选列表 CRUD
├── cache.py               # 内存 TTL 缓存
└── routes.py              # FastAPI 路由
```

## API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/us-stock/quotes` | 批量获取自选股票行情 |
| GET | `/api/v1/us-stock/quote/{symbol}` | 单只股票实时行情 |
| GET | `/api/v1/us-stock/kline/{symbol}?interval=1d&range=3mo` | K 线历史数据，interval: 1m/5m/1h/1d/1wk/1mo，range: 1d/5d/1mo/3mo/6mo/1y/5y/max |
| GET | `/api/v1/us-stock/fundamental/{symbol}` | 基本面数据 |
| GET | `/api/v1/us-stock/search?q=xxx` | 搜索美股，返回 symbol/name/exchange/type，最多 20 条 |
| GET | `/api/v1/us-stock/watchlist` | 查询自选列表 |
| POST | `/api/v1/us-stock/watchlist` | 添加自选 |
| DELETE | `/api/v1/us-stock/watchlist/{symbol}` | 删除自选 |
| GET | `/api/v1/us-stock/binance/assets` | 查询币安账户美股资产 |

## 数据模型

```python
class USQuote(BaseModel):
    symbol: str          # "AAPL"
    name: str            # "Apple Inc."
    price: float         # 最新价
    change: float        # 涨跌额
    change_pct: float    # 涨跌幅 %
    open: float
    high: float
    low: float
    volume: int          # 成交量
    market_cap: int      # 市值
    prev_close: float    # 昨收
    updated_at: datetime

class USKline(BaseModel):
    symbol: str
    interval: str        # "1d", "1h", "5m" 等
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime

class USFundamental(BaseModel):
    symbol: str
    name: str
    sector: str          # 行业
    industry: str        # 细分行业
    market_cap: int
    pe_ratio: float      # 市盈率
    pb_ratio: float      # 市净率
    dividend_yield: float
    eps: float           # 每股收益
    beta: float          # Beta
    fifty_two_week_high: float
    fifty_two_week_low: float

class USWatchlistItem(BaseModel):
    symbol: str
    name: str
    added_at: datetime
    sort_order: int
```

## 数据库表

`us_watchlist` 表，通过 Alembic migration 创建：

| 列名 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| symbol | VARCHAR(20) UNIQUE | 股票代码 |
| name | VARCHAR(100) | 股票名称 |
| sort_order | INTEGER | 排序权重 |
| created_at | TIMESTAMP | 添加时间 |

初始数据：`scripts/init_us_watchlist.py` 批量导入 ~500 只热门美股。

## 数据获取与缓存

### YahooProvider 封装

| 方法 | yfinance 调用 | 缓存 TTL |
|------|--------------|----------|
| `get_quote(symbol)` | `Ticker.info` | 60 秒 |
| `get_quotes(symbols)` | 批量 `tickers.download()` | 60 秒 |
| `get_kline(symbol, interval, range)` | `Ticker.history()` | 5 分钟 |
| `get_fundamental(symbol)` | `Ticker.info` | 1 小时 |
| `search(query)` | `yf.Search(query)` | 10 分钟 |

### 缓存层

- 使用 `cachetools.TTLCache` 做内存缓存
- 批量查询时用 `yf.download()` 一次性拉取多只股票
- 超过 50 只时分批请求，每批间隔 0.5s 避免限流

### 错误处理

- yfinance 超时/限流 → 返回缓存数据（如果有的话），标记 `stale: true`
- 网络异常 → 503 + 错误信息
- 股票代码不存在 → 404

### Binance 资产查询

- 复用现有 `crypto/data/binance_provider.py` 的签名和请求逻辑
- 调用 `GET /api/v3/account` 获取持仓，过滤出美股相关资产（asset 为股票代码如 AAPL、TSLA 等，或通过 watchlist 中的 symbol 匹配）
- 返回字段：symbol、free（可用余额）、locked（冻结）、total（总计）、usdt_value（USDT 估值）
- 缓存 30 秒

### 实时性说明

- yfinance 免费版提供延迟 15 分钟的行情数据
- Dashboard 做 60s 轮询刷新，足够看盘使用
- 后续可升级到 Yahoo Finance WebSocket 或付费实时数据源
- 美股交易时间：美东时间 9:30-16:00（北京时间 21:30-04:00 夏令时 / 22:30-05:00 冬令时）
- 非交易时段返回最近收盘数据，接口响应中标记 `market_open: false`

## Dashboard 集成

在现有 Dashboard 中新增 "美股" tab，与 A 股、加密并列。

```
┌─────────────────────────────────────────────┐
│  [A股]  [美股]  [加密]                       │
├─────────────────────────────────────────────┤
│  ┌─────────────┐  ┌───────────────────────┐ │
│  │ 币安资产概览  │  │  搜索框 + 自选管理     │ │
│  │ 总资产/盈亏   │  │  [+添加] [删除]       │ │
│  └─────────────┘  └───────────────────────┘ │
├─────────────────────────────────────────────┤
│  自选行情列表（表格）                          │
│  代码 | 名称 | 最新价 | 涨跌幅 | 成交量 | 市值  │
├─────────────────────────────────────────────┤
│  点击展开：K线图 + 基本面详情                   │
└─────────────────────────────────────────────┘
```

新增文件：
- `src/api/dashboard_page/us_stock_tab.py`
- `src/api/dashboard_page/templates/us_stock.html`

## 配置与依赖

### 新增依赖

```
yfinance>=0.2.40
cachetools>=5.3.0
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `YAHOO_FINANCE_ENABLED` | `true` | 是否启用 yfinance |
| `US_STOCK_CACHE_TTL_QUOTE` | `60` | 行情缓存秒数 |
| `US_STOCK_CACHE_TTL_KLINE` | `300` | K线缓存秒数 |
| `US_STOCK_CACHE_TTL_FUNDAMENTAL` | `3600` | 基本面缓存秒数 |
| `US_STOCK_BATCH_SIZE` | `50` | 批量查询每批数量 |
| `US_STOCK_BATCH_DELAY` | `0.5` | 批量查询间隔秒数 |
| `BINANCE_API_KEY` | - | 币安 API Key |
| `BINANCE_API_SECRET` | - | 币安 API Secret |

## 测试策略

### 单元测试

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/us_stock/test_yahoo_provider.py` | yfinance 封装：mock 返回值、解析、缓存、错误处理 |
| `tests/us_stock/test_watchlist.py` | 自选列表 CRUD：增删改查、去重、排序 |
| `tests/us_stock/test_cache.py` | TTL 缓存：过期清除、并发安全、内存上限 |
| `tests/us_stock/test_routes.py` | API 路由：参数校验、错误码、分批逻辑 |

### 集成测试

- `test_yfinance_real_quote`：真实调用 yfinance 查 AAPL 行情
- `test_binance_asset_query`：真实调用币安 testnet API 查账户资产

标记 `@pytest.mark.integration`，CI 中可跳过。

### 验证命令

```bash
# 单元测试
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/ -q

# 含集成测试
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/ -q -m integration
```

## 与现有代码的关系

- `routes_market.py` 中的 `/stocks/us` 端点保留不删除（向后兼容）
- 新模块 `src/us_stock/` 作为美股数据的升级替代
- Dashboard 美股 tab 走新模块的 `/api/v1/us-stock/*` 接口
- 不修改现有 A 股和加密模块的任何代码
