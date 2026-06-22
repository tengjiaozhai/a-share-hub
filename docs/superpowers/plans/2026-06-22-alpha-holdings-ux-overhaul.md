# Alpha 持仓分析 UX 全面重构方案

## 摘要

把持仓分析页从"能填数字"升级为"看得懂、能决策、可操作"的真实持仓管理界面。本次改动严格按后端先行、API 契约锁定、前端对齐实现的原则，避免双轨实现。

## 核心决策（已锁定）

1. **A 股 CNY / 美股 USD 分屏显示，不做强转汇率的总资产视图**
2. **每只股票卡片显示涨跌 %、浮盈金额、距离止损/止盈**
3. **输入区按钮按用户首次使用流程重排**
4. **保存后立即显示 Toast 反馈，并按需自动触发分析**
5. **顶部 30/60/120 + checkbox 加明确标签**
6. **盈亏阈值告警：浮亏 ≥ 止损线标红，浮盈 ≥ 止盈线标绿**

## API 契约（前后端共同遵守）

### 新增字段（holdings 表 + POST/GET）

```sql
ALTER TABLE alpha_holdings_entries ADD COLUMN
  stop_loss_ratio   FLOAT DEFAULT -0.08,
  take_profit_ratio FLOAT DEFAULT 0.20;
```

### GET /api/v1/alpha/holdings 返回结构

```json
{
  "items": [
    {
      "entry_id": "string",
      "symbol": "MU.US",
      "market": "us",            // 新增：a / us
      "buy_date": "2026-06-02",
      "buy_price": 1014.8585,
      "quantity": 0.0120,
      "stop_loss_ratio": -0.08,
      "take_profit_ratio": 0.20
    }
  ]
}
```

### 新增 GET /api/v1/alpha/holdings/summary

```json
{
  "summary": [
    {
      "market": "a",
      "currency": "CNY",
      "holdings_count": 0,
      "lots_count": 0,
      "total_cost": 0,
      "market_value": 0,
      "unrealized_pnl": 0,
      "unrealized_pnl_ratio": 0
    },
    {
      "market": "us",
      "currency": "USD",
      "holdings_count": 1,
      "lots_count": 2,
      "total_cost": 20.32,
      "market_value": 24.95,
      "unrealized_pnl": 4.63,
      "unrealized_pnl_ratio": 0.126
    }
  ]
}
```

### 聚合响应字段（per-symbol）

```json
{
  "symbol": "MU.US",
  "market": "us",
  "currency": "USD",
  "total_quantity": 0.022,
  "weighted_avg_cost": 1006.68,
  "total_cost": 22.15,
  "latest_price": 1133.99,
  "close_as_of": "2026-06-21",
  "market_value": 24.94,
  "unrealized_pnl": 2.79,
  "unrealized_pnl_ratio": 0.126,
  "first_buy_date": "2026-06-02",
  "last_buy_date": "2026-06-04",
  "lot_count": 2,
  "alert_level": "ok"   // ok / stop_loss / take_profit
}
```

### 行情接口（沿用 + 加货币标注）

现有 `latest_close(symbol)` 接口行为不变，前端按 `market` 字段决定显示币种。

## 文件改动清单

### 后端（owner: backend-subagent）

| 文件 | 改动 |
|------|------|
| `alembic/versions/20260622_add_holdings_thresholds.py` | 新增 migration |
| `src/storage/models.py` | AlphaHoldingsEntry 新增 stop_loss_ratio / take_profit_ratio |
| `src/storage/runtime_store.py` | upsert / update / fetch 支持新字段 |
| `src/alpha/portfolio_service.py` | 聚合返回增加 market / currency / 涨跌% / alert_level |
| `src/api/routes_alpha.py` | 新增 GET /api/v1/alpha/holdings/summary；POST/PUT 接受阈值 |
| `src/market/fx_service.py` | 新增（汇率服务，**本期仅占位**） |

### 前端（owner: frontend-subagent）

| 文件 | 改动 |
|------|------|
| `src/api/dashboard_page/partials/view_alpha.html` | 重构 DOM 顺序 |
| `src/api/dashboard_page/scripts/alpha.js` | 市场分段渲染、新增总览卡、阈值告警、Toast |
| `src/api/dashboard_page/styles/alpha.css` | 卡片高亮、涨跌% 视觉、阈值色 |

### 不改动的部分

- 不新增"折算单一币种的总资产"卡片
- 不做实时汇率，仅 T+0 收盘价刷新
- 不引入新依赖（不装 cva、不装状态库）
- 不动 dashboard 其他 tab
- 不改持仓录入逻辑（保存 / 编辑 / 删除保留）

## UI 结构（前端落地目标）

```
┌─ 顶部 tab ───────────────────────────────────────┐
│ 持仓分析      [A股] [美股]     ← 切换市场         │
├─ 总览（按选中市场）────────────────────────────── │
│ 净值 | 已实现 | 未实现 | 持仓/成交                │
│ 简单四宫格，按所选市场币种显示                    │
├─ 分析参数 ────────────────────────────────────── │
│ 回看窗口：[30日][60日][120日]                    │
│ ☑ 包含影子持仓                                  │
│ ☑ 包含回测对比                                  │
│ [生成分析]                                      │
├─ 当前持仓（按选中市场过滤）───────────────────── │
│ ┌─ MU.US ────────────────────── [编辑][删除] ─┐ │
│ │ 现价     1133.99 USD                        │ │
│ │ 持仓成本 1006.68 USD (均价)                 │ │
│ │ 持仓数量 0.0220 股                          │ │
│ │ 浮盈金额 +18.56 USD  ┐                      │ │
│ │ 浮盈比例 +12.61%     ┘ ← 颜色：绿/红        │ │
│ │ 距最高点 -2.3%                                │ │
│ │ 距最低点 +18.2%                              │ │
│ │ 首次买入 2026-06-02                         │ │
│ │ 最近买入 2026-06-04                         │ │
│ │ 批次 2 笔                                    │ │
│ │ 止损 -8% | 止盈 +20% | 当前 +12.6%           │ │
│ └────────────────────────────────────────────────┘ │
├─ 新增持仓 ────────────────────────────────────── │
│ [代码输入]                                      │
│ [+ 新增股票]                                    │
│ [日期] [价格] [数量]                            │
│ [+ 新增批次]  [删除批次]                       │
│ [保存]  [保存并生成分析]                       │
├─ 已保存买入记录 ──────────────────────────────── │
│ 列表 + 编辑/删除按钮                            │
└────────────────────────────────────────────────┘
```

## 验收标准

### 功能

1. 进入持仓分析默认显示 A 股（CNY）
2. 切到美股 tab，所有数字立即变 USD，不做任何汇率转换
3. 填代码 → 点新增股票 → 填批次 → 保存，3 步完成
4. 单股卡片显示：现价、成本、占比、涨跌%、距离止损/止盈
5. 保存成功有 Toast
6. 浮亏 ≥ 止损线 → 整卡标红 + 顶部告警
7. 浮盈 ≥ 止盈线 → 整卡标绿 + 顶部告警
8. 30/60/120 + checkbox 都有 label

### 测试

- 后端：单测覆盖新字段读写、聚合计算、summary 端点
- 前端：dashboard contract 测试覆盖 DOM 顺序、按钮 label、新字段
- 集成：浏览器端到端验证

### 不验收

- 跨市场折算单一币种的总资产
- 实时汇率
- 汇率波动告警
- 显示币种手动切换

## 风险与约束

1. **汇率复杂度控制**：FxService 本期仅占位（接口定义 + no-op 实现），不强转币种
2. **现有数据兼容**：存量 holdings 记录通过 migration 自动补默认阈值
3. **API 兼容性**：旧 dashboard 字段保留，新字段 additive 增量
4. **前端零状态**：未录入任何持仓时，零状态文案"暂无持仓，点击新增股票开始"
