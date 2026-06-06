# A 股工作台设计文档

## 概述

将现有"实时行情"tab 重构为 A 股专用工作台，采用与美股 tab 一致的三栏布局，支持行情列表、K 线图、基本面数据展示。

## 背景

- 现有"实时行情"tab 是简单表格布局，包含 A 股/美股下拉选项
- 美股已有独立 tab，"实时行情"应专注 A 股
- A 股数据来自腾讯行情 API，已有 K 线接口但未在 UI 中展示
- 需要添加 K 线和基本面功能，与美股 tab 保持一致

## 方案选择

**方案：重构为 A 股工作台（选定）**

- 重写 `view_market.html` 为三栏布局
- 移除美股下拉选项
- 新增 A 股自选列表（独立表）
- 复用美股 tab 的 CSS 和 JS 模式

理由：与美股 tab 保持一致的用户体验，复用已有代码模式。

## API 设计

### 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/a-stock/kline/{symbol}?period=daily&count=60` | A 股 K 线数据 |
| GET | `/api/v1/a-stock/fundamental/{symbol}` | A 股基本面数据 |
| GET | `/api/v1/a-stock/watchlist` | 查询 A 股自选列表 |
| POST | `/api/v1/a-stock/watchlist` | 添加 A 股自选 |
| DELETE | `/api/v1/a-stock/watchlist/{symbol}` | 删除 A 股自选 |
| POST | `/api/v1/a-stock/quotes` | 批量获取自选行情 |

### 复用现有接口

- `GET /api/v1/market/stocks?q=xxx` — A 股搜索
- `POST /api/v1/market/bulk` — 批量行情

### K 线接口

**参数：**
- `symbol`: 股票代码，如 "600519.SH"
- `period`: daily / weekly / monthly
- `count`: 返回 K 线数量（默认 60）

**返回：**
```json
[
  {
    "date": "2026-01-01",
    "open": 1900.0,
    "high": 1920.0,
    "low": 1890.0,
    "close": 1910.0,
    "volume": 50000000
  }
]
```

### 基本面接口

**返回：**
```json
{
  "symbol": "600519.SH",
  "name": "贵州茅台",
  "pe_ratio": 33.5,
  "turnover": 0.35,
  "amplitude": 1.2,
  "volume_ratio": 1.1,
  "market_cap": 2100000000000,
  "high_52w": 2100.0,
  "low_52w": 1500.0
}
```

## UI 布局

### 三栏布局（与美股 tab 一致）

```
┌──────────────┬────────────────────────────┬──────────────┐
│  左栏         │  中栏                       │  右栏         │
│              │                            │              │
│  搜索 A 股    │  [行情列表] [K线图] [基本面]   │  股票详情     │
│  自选管理     │                            │              │
│  市场状态     │  行情表格 / K线表格 / 基本面   │  关键指标     │
│  数据刷新     │                            │              │
└──────────────┴────────────────────────────┴──────────────┘
```

### 左栏内容

- 搜索框：输入代码或名称，支持回车搜索
- 自选管理：chips 展示，支持添加/删除
- 市场状态：A 股开盘/收盘（9:30-15:00）
- 数据刷新：最后更新时间 + 手动刷新按钮

### 中栏 Tab

- 行情列表：代码、名称、最新价、涨跌额、涨跌幅、开盘、最高、最低、成交量、换手率、振幅、量比、操作
- K 线图：周期切换（日K/周K/月K），K 线数据表格
- 基本面：PE、换手率、振幅、量比、市值

### 右栏内容

- 股票详情：名称、价格、涨跌幅
- 关键指标：PE、换手率、振幅、量比

## 数据库

### 表结构 `a_share_watchlist`

| 列名 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| symbol | VARCHAR(20) UNIQUE | 股票代码，如 "600519.SH" |
| name | VARCHAR(100) | 股票名称 |
| sort_order | INTEGER | 排序权重 |
| created_at | TIMESTAMP | 添加时间 |

### 初始数据

导入 A 股热门股票（沪深300成分股或用户指定列表）。

## 数据流

```
用户搜索 → /api/v1/market/stocks → 展示搜索结果
用户点击 → 添加到 a_share_watchlist 表
行情加载 → /api/v1/a-stock/quotes → 批量获取腾讯行情
K线加载 → /api/v1/a-stock/kline/{symbol} → 腾讯K线接口
基本面 → /api/v1/a-stock/fundamental/{symbol} → 腾讯行情字段
```

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/a_stock/__init__.py` | 创建 | 模块初始化 |
| `src/a_stock/models.py` | 创建 | Pydantic 数据模型 |
| `src/a_stock/watchlist.py` | 创建 | 自选列表 CRUD |
| `src/a_stock/routes.py` | 创建 | FastAPI 路由 |
| `src/main.py` | 修改 | 注册 A 股路由 |
| `alembic/versions/20260603_000007_add_a_share_watchlist.py` | 创建 | 自选列表表 migration |
| `scripts/init_a_share_watchlist.py` | 创建 | 初始数据导入脚本 |
| `src/api/dashboard_page/partials/view_market.html` | 重写 | 三栏布局 |
| `src/api/dashboard_page/scripts/market.js` | 重写 | 完整交互逻辑 |
| `tests/a_stock/__init__.py` | 创建 | 测试包 |
| `tests/a_stock/test_routes.py` | 创建 | API 路由测试 |
| `tests/a_stock/test_watchlist.py` | 创建 | 自选列表测试 |

## 测试策略

### 单元测试

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/a_stock/test_routes.py` | API 路由：参数校验、错误码、分页 |
| `tests/a_stock/test_watchlist.py` | 自选列表 CRUD：增删改查、去重 |

### 验收标准

1. 搜索 A 股代码或名称，返回结果
2. 点击搜索结果，添加到自选列表
3. 行情列表加载，显示涨跌幅、成交量等
4. 点击股票代码，切换到 K 线 tab，显示 K 线数据
5. 切换到基本面 tab，显示 PE、换手率等
6. 分页功能正常
7. 删除自选功能正常

### 验证命令

```bash
# 单元测试
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/a_stock/ -v

# Lint
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/a_stock/
```

## 与现有代码的关系

- `routes_market.py` 中的 `/stocks` 端点保留（A 股搜索）
- `routes_market.py` 中的 `/stocks/us` 端点保留（美股搜索，供美股 tab 使用）
- `routes_market.py` 中的 `/bulk` 端点保留（批量行情）
- `view_market.html` 和 `market.js` 完全重写
- 不修改美股 tab 的任何代码
