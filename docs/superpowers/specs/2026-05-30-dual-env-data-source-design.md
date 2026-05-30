# 双环境数据源自动切换设计

## 问题

AkShare 全市场扫描接口在海外服务器（AWS 新加坡）上被东方财富限流断连，本地正常。需要一套代码同时支持本地和服务器环境。

## 方案

环境感知的自动降级：本地走 AkShare，服务器走 Tushare。

## 配置

`.env` 新增：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `MARKET_DATA_PROVIDER` | `auto` | `auto` / `akshare` / `tushare` |
| `TUSHARE_TOKEN` | 空 | Tushare Pro token |

## 文件变更

| 文件 | 操作 | 内容 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 `tushare_token` 字段 |
| `src/data/providers/tushare_provider.py` | 新建 | Tushare 数据提供者，实现 `DataProvider` 接口 |
| `src/data/providers/provider_chain.py` | 修改 | 支持 `auto` 模式探测降级 |
| `.env.example` | 修改 | 新增 Tushare 配置模板 |

**不改动：** `base.py`、`akshare_provider.py`、`routes_dashboard.py`、现有测试。

## auto 模式逻辑

```
1. 读取 MARKET_DATA_PROVIDER 配置
2. 如果是 "akshare" → 直接用 AkShare
3. 如果是 "tushare" → 直接用 Tushare
4. 如果是 "auto":
   a. 探测 AkShare 全市场接口（5秒超时）
   b. 成功 → 用 AkShare
   c. 失败 → 用 Tushare
   d. 两者都失败 → 返回错误
```

## TushareProvider 实现

- `is_available()`：检查 `tushare_token` 非空
- `get_realtime_quote(symbol)`：用 `pro.daily()` 获取最新一条
- `get_history(symbol, start, end, freq)`：用 `pro.daily()` 获取历史
- `get_stock_list()`：用 `pro.stock_basic()` 获取股票列表

## 测试

- 本地 `auto` → AkShare 生效
- 服务器 `auto` → Tushare 降级
- 手动指定 → 跳过探测
- 两者都失败 → 明确错误

## 约束

- 不引入新依赖
- 探测超时 ≤ 5 秒
- 现有 AkShare 测试不受影响
