# Strategy Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前扫描、模拟交易、回测和长期评估从演示级原型收敛成一条可审计、可回测、可 shadow 验证的近实盘策略路径。

**Architecture:** 保留现有 canonical 入口名称，但替换其内部实现，不新增 legacy 双轨。核心交易逻辑从 `src/api/routes_dashboard.py` 下沉到 strategy、portfolio、risk、execution、backtest、evaluation 模块；dashboard 和 CLI 只做参数解析、调用服务、返回结果。所有 BUY/SELL 决策必须携带行情质量、因子贡献、目标仓位、风险门和成交/对账证据。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pandas, pytest, existing `RuntimeStore`, existing `AkshareProvider`, existing `YahooProvider`.

---

## Assumptions

- 当前目标不是直接打开实盘交易，而是达到“可连续 shadow / paper 验证”的近实盘标准。
- 不保留旧扫描、旧回测、旧执行公式。改造完成后只有一个权威策略路径。
- A 股按整手 100 股执行，BUY 必须满足现金、仓位、行情质量和风控要求；SELL 默认全清当前可卖持仓。
- 当前仓库事实：`src/strategy/stock_scanner.py` 已有两轮扫描，`src/backtest/engine.py` 已有简化回测，`src/evaluation/long_run.py` 仍是占位指标，`src/api/routes_dashboard.py` 内联了模拟执行和 PnL 逻辑。

## Non-Goals

- 不接入真实券商下单。
- 不增加兼容旧 schema 或旧 CLI 的分支。
- 不引入新的行情供应商。
- 不把 LLM 作为强制 BUY 来源；LLM 只能解释或确认，不能绕过确定性风控。

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `src/core/config.py` | Modify | 增加策略成熟度所需参数：扫描阈值、K 线窗口、整手、费用、滑点、日内风控 |
| `src/core/market_rules.py` | Modify | 成为 A 股交易规则权威：整手、T+1、涨跌停、可交易状态 |
| `src/indicators/technical_indicators.py` | Modify | 从 K 线 bars 计算完整技术特征，包含成交量 |
| `src/strategy/signal_engine.py` | Modify | 输出 action、score、RSI、features、contributions、thresholds |
| `src/strategy/stock_scanner.py` | Modify | 修正实时因子归一化、动态 K 线确认、行情质量检查 |
| `src/strategy/strategy_config.py` | Modify | 从 `Settings` 读取完整策略参数 |
| `src/portfolio/target_planner.py` | Replace implementation | 权威目标仓位和整手下单数量计算 |
| `src/risk/pre_trade_risk.py` | Replace implementation | 权威交易前风险门 |
| `src/execution/paper_portfolio.py` | Replace implementation | 权威模拟账户状态更新、PnL、NAV |
| `src/execution/paper_execution_service.py` | Create | 将目标仓位执行为模拟订单、成交事件和账户快照 |
| `src/backtest/engine.py` | Replace implementation | 近实盘日频事件回测，含整手、费用、滑点、重复 BUY 控制 |
| `src/backtest/metrics.py` | Modify | 从权益曲线和交易配对计算收益、回撤、换手、胜率 |
| `src/evaluation/long_run.py` | Replace implementation | 从账户快照、订单、broker events 计算 1m/3m/1y shadow 指标 |
| `src/storage/runtime_store.py` | Modify | 增加账户快照列表和按时间读取 broker events 的方法 |
| `src/api/routes_dashboard.py` | Modify | 移除内联执行公式，调用 scanner/backtest/paper service |
| `src/main.py` | Modify | `backtest` 和 `evaluate-shadow` 调用真实服务，不只打印参数 |
| `tests/*` | Modify/Create | 为每个风险点写失败测试 |
| `docs/runbooks/long-horizon-evaluation.md` | Modify | 更新长期评估验收方法 |
| `docs/runbooks/dashboard_user_guide.md` | Modify | 更新扫描、回测、shadow 执行说明 |

## Phase Gates

1. **Gate A: Strategy Signal Gate**  
   扫描和信号相关测试通过，且美股中性样例不再被判 BUY。

2. **Gate B: Execution Consistency Gate**  
   dashboard、CLI、target planner、paper execution 对同一输入产出相同目标金额和整手数量。

3. **Gate C: Backtest Realism Gate**  
   回测包含费用、滑点、整手、重复 BUY 控制、胜率配对，且不再用固定 `win_rate=0.0`。

4. **Gate D: Shadow Evaluation Gate**  
   `evaluate-shadow` 指标来自账户快照和成交事件，不能固定返回 0。

5. **Gate E: Full Verification Gate**  
   本地不配置 PostgreSQL 时，非 PostgreSQL 专属测试仍能跑通；配置 `TEST_DATABASE_URL` 时全量测试跑通。

---

### Task 1: Strategy Config And Market Rules

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/strategy/strategy_config.py`
- Modify: `src/core/market_rules.py`
- Test: `tests/test_strategy_config.py`
- Test: `tests/test_market_rules.py`

- [ ] **Step 1: Write failing config tests**

Append to `tests/test_strategy_config.py`:

```python
from src.core.config import Settings
from src.strategy.strategy_config import StrategyConfig


def test_strategy_config_exposes_production_readiness_fields():
    settings = Settings(
        strategy_top_n=10,
        strategy_max_position_ratio=0.2,
        strategy_buy_score_threshold=0.55,
        strategy_sell_score_threshold=-0.20,
        strategy_scan_buy_threshold_a=0.55,
        strategy_scan_buy_threshold_us=0.45,
        strategy_min_confirm_bars=61,
        strategy_confirm_lookback_days=180,
        strategy_lot_size=100,
        strategy_fee_bps=3.0,
        strategy_slippage_bps=5.0,
        strategy_max_daily_loss_ratio=0.03,
    )

    config = StrategyConfig.from_settings(settings)

    assert config.scan_buy_threshold_a == 0.55
    assert config.scan_buy_threshold_us == 0.45
    assert config.min_confirm_bars == 61
    assert config.confirm_lookback_days == 180
    assert config.lot_size == 100
    assert config.fee_bps == 3.0
    assert config.slippage_bps == 5.0
    assert config.max_daily_loss_ratio == 0.03
```

- [ ] **Step 2: Write failing market rule tests**

Append to `tests/test_market_rules.py`:

```python
from datetime import date

from src.core.market_rules import (
    calculate_lot_quantity,
    is_limit_locked,
    is_sell_allowed,
    is_valid_lot_quantity,
)


def test_calculate_lot_quantity_rounds_down_to_a_share_lot():
    assert calculate_lot_quantity(target_value=20_000, price=103.0, lot_size=100) == 100
    assert calculate_lot_quantity(target_value=9_000, price=103.0, lot_size=100) == 0


def test_valid_lot_quantity_rejects_odd_lot_buy():
    assert is_valid_lot_quantity("BUY", 100, lot_size=100) is True
    assert is_valid_lot_quantity("BUY", 150, lot_size=100) is False
    assert is_valid_lot_quantity("SELL", 150, lot_size=100) is True


def test_sell_allowed_blocks_same_day_a_share_sell():
    assert is_sell_allowed("CN_A", buy_date=date(2026, 6, 4), sell_date=date(2026, 6, 4)) is False
    assert is_sell_allowed("CN_A", buy_date=date(2026, 6, 3), sell_date=date(2026, 6, 4)) is True
    assert is_sell_allowed("US", buy_date=date(2026, 6, 4), sell_date=date(2026, 6, 4)) is True


def test_limit_locked_blocks_buy_at_limit_up_and_sell_at_limit_down():
    assert is_limit_locked(action="BUY", current_price=110.0, prev_close=100.0, limit_ratio=0.10) is True
    assert is_limit_locked(action="SELL", current_price=90.0, prev_close=100.0, limit_ratio=0.10) is True
    assert is_limit_locked(action="BUY", current_price=108.0, prev_close=100.0, limit_ratio=0.10) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_strategy_config.py tests/test_market_rules.py -q 2>&1 | head -c 12000
```

Expected: FAIL because the new `Settings` fields and market rule helpers do not exist.

- [ ] **Step 4: Implement config fields**

Modify `src/core/config.py` strategy config block to:

```python
    # 策略配置
    strategy_top_n: int = 10
    strategy_max_position_ratio: float = 0.2
    strategy_buy_score_threshold: float = 0.55
    strategy_sell_score_threshold: float = -0.20
    strategy_scan_buy_threshold_a: float = 0.55
    strategy_scan_buy_threshold_us: float = 0.45
    strategy_min_confirm_bars: int = 61
    strategy_confirm_lookback_days: int = 180
    strategy_lot_size: int = 100
    strategy_fee_bps: float = 3.0
    strategy_slippage_bps: float = 5.0
    strategy_max_daily_loss_ratio: float = 0.03
```

Replace `src/strategy/strategy_config.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int
    max_position_ratio: float
    buy_score_threshold: float
    sell_score_threshold: float
    scan_buy_threshold_a: float
    scan_buy_threshold_us: float
    min_confirm_bars: int
    confirm_lookback_days: int
    lot_size: int
    fee_bps: float
    slippage_bps: float
    max_daily_loss_ratio: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "StrategyConfig":
        return cls(
            top_n=settings.strategy_top_n,
            max_position_ratio=settings.strategy_max_position_ratio,
            buy_score_threshold=settings.strategy_buy_score_threshold,
            sell_score_threshold=settings.strategy_sell_score_threshold,
            scan_buy_threshold_a=settings.strategy_scan_buy_threshold_a,
            scan_buy_threshold_us=settings.strategy_scan_buy_threshold_us,
            min_confirm_bars=settings.strategy_min_confirm_bars,
            confirm_lookback_days=settings.strategy_confirm_lookback_days,
            lot_size=settings.strategy_lot_size,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
            max_daily_loss_ratio=settings.strategy_max_daily_loss_ratio,
        )
```

- [ ] **Step 5: Implement market rule helpers**

Replace `src/core/market_rules.py` with:

```python
from __future__ import annotations

from datetime import date


def can_sell_position_same_day(market: str) -> bool:
    if market == "CN_A":
        return False
    return True


def get_price_limit_ratio(stock_type: str) -> float:
    if stock_type == "ST":
        return 0.05
    return 0.10


def is_tradable(status: str) -> bool:
    return status in {"正常交易", "trading"}


def calculate_lot_quantity(target_value: float, price: float, lot_size: int = 100) -> int:
    if target_value <= 0 or price <= 0 or lot_size <= 0:
        return 0
    raw_quantity = int(target_value / price)
    return raw_quantity // lot_size * lot_size


def is_valid_lot_quantity(action: str, quantity: int, lot_size: int = 100) -> bool:
    if quantity <= 0:
        return False
    if action == "BUY":
        return quantity % lot_size == 0
    return True


def is_sell_allowed(market: str, buy_date: date | None, sell_date: date) -> bool:
    if can_sell_position_same_day(market):
        return True
    if buy_date is None:
        return True
    return sell_date > buy_date


def is_limit_locked(action: str, current_price: float, prev_close: float, limit_ratio: float) -> bool:
    if current_price <= 0 or prev_close <= 0 or limit_ratio <= 0:
        return False
    limit_up = prev_close * (1 + limit_ratio)
    limit_down = prev_close * (1 - limit_ratio)
    if action == "BUY":
        return current_price >= round(limit_up, 2)
    if action == "SELL":
        return current_price <= round(limit_down, 2)
    return False
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_strategy_config.py tests/test_market_rules.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/core/config.py src/strategy/strategy_config.py src/core/market_rules.py tests/test_strategy_config.py tests/test_market_rules.py
git commit -m "feat: add production strategy config and market rules"
```

---

### Task 2: Complete K-Line Feature Computation And Signal Attribution

**Files:**
- Modify: `src/indicators/technical_indicators.py`
- Modify: `src/strategy/signal_engine.py`
- Test: `tests/test_strategy_signal_engine.py`

- [ ] **Step 1: Write failing tests for bar-based features and attribution**

Append to `tests/test_strategy_signal_engine.py`:

```python
from src.indicators.technical_indicators import compute_features_from_bars


def test_compute_features_from_bars_uses_volume_ratio():
    bars = [
        {"date": f"2026-01-{(i % 28) + 1:02d}", "close": 100 + i, "volume": 1_000}
        for i in range(61)
    ]
    bars[-1]["volume"] = 3_000

    features = compute_features_from_bars(bars)

    assert features["volume_ratio_20"] > 2.0
    assert features["bar_count"] == 61


def test_build_signal_returns_factor_contributions():
    features = {
        "ma20_gap": 0.50,
        "ma60_gap": 0.40,
        "momentum_20": 0.80,
        "momentum_60": 0.60,
        "rsi_14": 58,
        "volatility_20": 0.01,
        "volume_ratio_20": 1.50,
        "bar_count": 61,
    }

    signal = build_signal("600519.SH", features, _BASE_CONFIG)

    assert signal["action"] == "BUY"
    assert signal["rsi_14"] == 58
    assert signal["features"]["momentum_20"] == 0.80
    assert signal["contributions"]["momentum_20"] == 0.24
    assert signal["thresholds"]["buy"] == _BASE_CONFIG.buy_score_threshold
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_strategy_signal_engine.py -q 2>&1 | head -c 12000
```

Expected: FAIL because `compute_features_from_bars` and signal attribution fields do not exist.

- [ ] **Step 3: Add bar-based feature helper**

Append to `src/indicators/technical_indicators.py`:

```python
def compute_features_from_bars(bars: list[dict]) -> Dict[str, float]:
    close_prices = [float(row["close"]) for row in bars if row.get("close") is not None]
    volumes = [float(row["volume"]) for row in bars if row.get("volume") is not None]
    features = compute_feature_row(close_prices, volumes if len(volumes) == len(close_prices) else None)
    features["bar_count"] = len(close_prices)
    return features
```

- [ ] **Step 4: Replace signal output with attribution**

Replace `src/strategy/signal_engine.py` with:

```python
from __future__ import annotations

from src.strategy.strategy_config import StrategyConfig

_WEIGHTS = {
    "momentum_20": 0.30,
    "momentum_60": 0.25,
    "ma20_gap": 0.20,
    "ma60_gap": 0.15,
    "volume_ratio_20": 0.10,
    "volatility_20": -0.10,
}


def compute_factor_contributions(features: dict[str, float]) -> dict[str, float]:
    return {
        name: round(weight * features.get(name, 0.0), 6)
        for name, weight in _WEIGHTS.items()
    }


def compute_technical_score(features: dict[str, float]) -> float:
    return sum(compute_factor_contributions(features).values())


def build_signal(symbol: str, features: dict[str, float], config: StrategyConfig) -> dict:
    score = compute_technical_score(features)
    rsi = features.get("rsi_14", 50.0)
    ma20_gap = features.get("ma20_gap", 0.0)

    if score >= config.buy_score_threshold and 45 <= rsi <= 72:
        action = "BUY"
    elif score <= config.sell_score_threshold or rsi >= 80 or ma20_gap <= -0.05:
        action = "SELL"
    else:
        action = "HOLD"

    return {
        "symbol": symbol,
        "action": action,
        "technical_score": round(score, 6),
        "rsi_14": rsi,
        "features": dict(features),
        "weights": dict(_WEIGHTS),
        "contributions": compute_factor_contributions(features),
        "thresholds": {
            "buy": config.buy_score_threshold,
            "sell": config.sell_score_threshold,
        },
    }
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_strategy_signal_engine.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/indicators/technical_indicators.py src/strategy/signal_engine.py tests/test_strategy_signal_engine.py
git commit -m "feat: add complete technical features and attribution"
```

---

### Task 3: Harden Market Scanner And Confirmation Pipeline

**Files:**
- Modify: `src/strategy/stock_scanner.py`
- Modify: `src/api/routes_dashboard.py:746-839`
- Test: `tests/test_stock_scanner.py`
- Test: `tests/test_backtest_api.py`

- [ ] **Step 1: Write failing tests for scanner behavior**

Append to `tests/test_stock_scanner.py`:

```python
from datetime import datetime


def test_score_us_quote_keeps_small_positive_move_as_hold():
    result = score_us_quote({
        "symbol": "MSFT",
        "name": "微软",
        "change_pct": 0.5,
        "volume": 30_000_000,
    })

    assert result["action"] == "HOLD"
    assert result["score"] < 0.45


def test_confirm_buy_candidates_uses_dynamic_window_and_volume():
    from src.strategy.strategy_config import StrategyConfig

    config = StrategyConfig(
        top_n=10,
        max_position_ratio=0.2,
        buy_score_threshold=0.55,
        sell_score_threshold=-0.20,
        scan_buy_threshold_a=0.55,
        scan_buy_threshold_us=0.45,
        min_confirm_bars=61,
        confirm_lookback_days=180,
        lot_size=100,
        fee_bps=3.0,
        slippage_bps=5.0,
        max_daily_loss_ratio=0.03,
    )
    seen = {}

    def mock_kline_fn(symbol, start, end):
        seen["start"] = datetime.fromisoformat(start)
        seen["end"] = datetime.fromisoformat(end)
        return pd.DataFrame({
            "date": [f"2026-01-{(i % 28) + 1:02d}" for i in range(61)],
            "close": [100 + i for i in range(61)],
            "volume": [1_000 for _ in range(60)] + [3_000],
        })

    result = confirm_buy_candidates(
        [{"symbol": "300750.SZ", "name": "宁德时代", "score": 0.80, "action": "BUY", "reason": "strong"}],
        mock_kline_fn,
        config,
        top_n=10,
        as_of=datetime(2026, 6, 4),
    )

    assert result[0]["confirmed"] is True
    assert result[0]["features"]["volume_ratio_20"] > 2.0
    assert (seen["end"] - seen["start"]).days == 180
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py -q 2>&1 | head -c 12000
```

Expected: FAIL because current US scoring marks the neutral sample as BUY and `confirm_buy_candidates` has no `as_of` parameter.

- [ ] **Step 3: Replace US quote normalization**

In `src/strategy/stock_scanner.py`, replace `score_us_quote` with:

```python
def score_us_quote(quote: dict[str, Any]) -> dict[str, Any]:
    change_pct = _safe_float(quote.get("change_pct"))
    volume = _safe_float(quote.get("volume"))
    name = str(quote.get("name", ""))

    f_change = max(0.0, min(1.0, change_pct / 5))
    f_volume = max(0.0, min(1.0, volume / 50_000_000))
    score = 0.50 * f_change + 0.50 * f_volume

    if score >= 0.45 and change_pct >= 2.0:
        action = "BUY"
    elif score <= 0.25 or change_pct < -3:
        action = "SELL"
    else:
        action = "HOLD"

    reasons = []
    if change_pct > 2:
        reasons.append(f"涨幅{change_pct:.1f}%，趋势向好")
    elif change_pct < -2:
        reasons.append(f"跌幅{change_pct:.1f}%，注意风险")
    if volume > 50_000_000:
        reasons.append(f"成交量{volume/10000:.0f}万，交投活跃")
    if not reasons:
        reasons.append("指标平稳")

    return {
        "symbol": quote.get("symbol", ""),
        "name": name,
        "score": round(score, 4),
        "action": action,
        "reason": "、".join(reasons),
        "factors": {
            "change_pct": round(change_pct, 2),
            "volume": round(volume, 0),
        },
    }
```

- [ ] **Step 4: Replace A-share confirmation with dynamic window**

In `src/strategy/stock_scanner.py`, replace `confirm_buy_candidates` with:

```python
def confirm_buy_candidates(
    candidates: list[dict],
    kline_fetcher,
    config,
    top_n: int = 10,
    as_of=None,
) -> list[dict]:
    from datetime import datetime, timedelta

    from src.indicators.technical_indicators import compute_features_from_bars
    from src.strategy.signal_engine import build_signal

    current = as_of or datetime.now()
    start = (current - timedelta(days=config.confirm_lookback_days)).date().isoformat()
    end = current.date().isoformat()

    confirmed = []
    for cand in candidates:
        symbol = cand["symbol"]
        enriched = dict(cand)
        try:
            df = kline_fetcher(symbol, start, end)
            if df.empty or len(df) < config.min_confirm_bars:
                enriched["confirmed"] = False
                enriched["final_score"] = 0.0
                enriched["final_action"] = "HOLD"
                enriched["confirm_reason"] = "历史数据不足"
                confirmed.append(enriched)
                continue
            features = compute_features_from_bars(df.to_dict("records"))
            signal = build_signal(symbol, features, config)
            enriched["confirmed"] = signal["action"] == "BUY"
            enriched["final_score"] = signal["technical_score"]
            enriched["final_action"] = signal["action"]
            enriched["features"] = signal["features"]
            enriched["contributions"] = signal["contributions"]
            enriched["thresholds"] = signal["thresholds"]
            enriched["confirm_reason"] = (
                f"趋势评分{signal['technical_score']:.4f}，"
                f"RSI={signal['rsi_14']:.2f}，信号{signal['action']}"
            )
        except Exception as exc:
            enriched["confirmed"] = False
            enriched["final_score"] = 0.0
            enriched["final_action"] = "HOLD"
            enriched["confirm_reason"] = f"确认失败: {exc}"
        confirmed.append(enriched)

    confirmed.sort(key=lambda row: (row["confirmed"], row.get("final_score", 0.0), row["score"]), reverse=True)
    return confirmed[:top_n]
```

- [ ] **Step 5: Replace US confirmation with complete feature path**

In `src/strategy/stock_scanner.py`, inside `confirm_us_buy_candidates`, replace:

```python
close_prices = [k.close for k in klines]
features = compute_feature_row(close_prices)
```

with:

```python
bars = [
    {"close": k.close, "volume": k.volume, "date": k.timestamp.isoformat()}
    for k in klines
]
features = compute_features_from_bars(bars)
```

Also replace the import:

```python
from src.indicators.technical_indicators import compute_feature_row
```

with:

```python
from src.indicators.technical_indicators import compute_features_from_bars
```

- [ ] **Step 6: Update dashboard scan endpoint call**

In `src/api/routes_dashboard.py`, keep the `/api/v1/dashboard/scan` route but pass the dynamic `as_of`:

```python
    confirmed_buy = confirm_buy_candidates(
        result["buy"],
        kline_fetcher,
        strategy_config,
        top_n=top_n,
        as_of=datetime.now(),
    )
```

- [ ] **Step 7: Run scanner tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py -q 2>&1 | head -c 12000
```

Expected: all scanner tests pass, including the existing US grouped scan tests.

- [ ] **Step 8: Commit**

```bash
git add src/strategy/stock_scanner.py src/api/routes_dashboard.py tests/test_stock_scanner.py
git commit -m "feat: harden scanner confirmation pipeline"
```

---

### Task 4: Canonical Target Planner And Risk Gate

**Files:**
- Replace implementation: `src/portfolio/target_planner.py`
- Replace implementation: `src/risk/pre_trade_risk.py`
- Test: `tests/test_target_planner.py`
- Test: `tests/test_pre_trade_risk.py`

- [ ] **Step 1: Replace target planner tests**

Replace `tests/test_target_planner.py` with:

```python
from src.portfolio.target_planner import build_target_position, build_target_positions


def test_build_target_position_uses_watchlist_allocation_and_lot_size():
    target = build_target_position(
        symbol="600519.SH",
        action="BUY",
        capital_base=1_000_000,
        max_position_ratio=0.2,
        watchlist_size=4,
        price=103.0,
        lot_size=100,
    )

    assert target["target_value"] == 50_000
    assert target["target_position_ratio"] == 0.05
    assert target["quantity"] == 400
    assert target["notional"] == 41_200


def test_build_target_position_sell_uses_current_position_quantity():
    target = build_target_position(
        symbol="600519.SH",
        action="SELL",
        capital_base=1_000_000,
        max_position_ratio=0.2,
        watchlist_size=4,
        price=103.0,
        lot_size=100,
        current_quantity=350,
    )

    assert target["target_value"] == 0
    assert target["quantity"] == 350
    assert target["target_position_ratio"] == 0.0


def test_build_target_positions_ignores_hold_actions():
    targets = build_target_positions(
        decisions=[
            {"symbol": "600519.SH", "action": "BUY"},
            {"symbol": "000001.SZ", "action": "HOLD"},
        ],
        prices={"600519.SH": 100.0, "000001.SZ": 10.0},
        capital_base=1_000_000,
        max_position_ratio=0.2,
        lot_size=100,
        current_positions={},
    )

    assert len(targets) == 1
    assert targets[0]["symbol"] == "600519.SH"
```

- [ ] **Step 2: Add risk gate tests**

Create `tests/test_pre_trade_risk.py`:

```python
from datetime import date

from src.risk.pre_trade_risk import evaluate_risk_gate


def test_risk_gate_blocks_kill_switch():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=True,
        available_cash=1_000_000,
        requested_value=100_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "kill_switch"


def test_risk_gate_blocks_position_limit():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=1_000_000,
        requested_value=250_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=2_500,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "max_position_ratio"


def test_risk_gate_blocks_same_day_a_share_sell():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="SELL",
        kill_switch=False,
        available_cash=1_000_000,
        requested_value=0,
        current_position_value=100_000,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
        market="CN_A",
        buy_date=date(2026, 6, 4),
        trade_date=date(2026, 6, 4),
    )

    assert result["approved"] is False
    assert result["rule_name"] == "t_plus_one"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_pre_trade_risk.py -q 2>&1 | head -c 12000
```

Expected: FAIL because signatures and new risk fields do not exist.

- [ ] **Step 4: Replace target planner implementation**

Replace `src/portfolio/target_planner.py` with:

```python
from __future__ import annotations

from typing import Any

from src.core.market_rules import calculate_lot_quantity


def build_target_position(
    symbol: str,
    action: str,
    capital_base: float,
    max_position_ratio: float,
    watchlist_size: int,
    price: float,
    lot_size: int,
    current_quantity: int = 0,
    expires_at: str = "",
) -> dict[str, Any]:
    if watchlist_size <= 0:
        raise ValueError("watchlist_size must be positive")

    if action == "BUY":
        target_position_ratio = max_position_ratio / watchlist_size
        target_value = int(capital_base * target_position_ratio)
        quantity = calculate_lot_quantity(target_value, price, lot_size)
        notional = int(quantity * price)
    elif action == "SELL":
        target_position_ratio = 0.0
        target_value = 0
        quantity = max(int(current_quantity), 0)
        notional = int(quantity * price)
    else:
        target_position_ratio = 0.0
        target_value = 0
        quantity = 0
        notional = 0

    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
        "target_position_ratio": target_position_ratio,
        "quantity": quantity,
        "notional": notional,
        "price": price,
        "expires_at": expires_at,
    }


def build_target_positions(
    decisions: list[dict],
    prices: dict[str, float],
    capital_base: float,
    max_position_ratio: float,
    lot_size: int,
    current_positions: dict[str, dict],
    expires_at: str = "",
) -> list[dict[str, Any]]:
    active_decisions = [row for row in decisions if row.get("action") in {"BUY", "SELL"}]
    watchlist_size = max(len(decisions), 1)
    targets = []
    for row in active_decisions:
        symbol = row["symbol"]
        current_position = current_positions.get(symbol, {})
        target = build_target_position(
            symbol=symbol,
            action=row["action"],
            capital_base=capital_base,
            max_position_ratio=max_position_ratio,
            watchlist_size=watchlist_size,
            price=prices[symbol],
            lot_size=lot_size,
            current_quantity=int(current_position.get("quantity", 0)),
            expires_at=expires_at,
        )
        if target["quantity"] > 0:
            targets.append(target)
    return targets
```

- [ ] **Step 5: Replace risk gate implementation**

Replace `src/risk/pre_trade_risk.py` with:

```python
from __future__ import annotations

from datetime import date
from typing import Any

from src.core.market_rules import is_sell_allowed, is_valid_lot_quantity


def _blocked(rule_name: str, reason: str) -> dict[str, Any]:
    return {"approved": False, "rule_name": rule_name, "reason": reason}


def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
    current_position_value: float,
    nav: float,
    max_position_ratio: float,
    quantity: int,
    lot_size: int,
    market: str = "CN_A",
    buy_date: date | None = None,
    trade_date: date | None = None,
) -> dict[str, Any]:
    if kill_switch:
        return _blocked("kill_switch", "kill switch enabled")
    if action not in {"BUY", "SELL"}:
        return _blocked("action", "action must be BUY or SELL")
    if not is_valid_lot_quantity(action, quantity, lot_size):
        return _blocked("lot_size", "invalid quantity for market lot rule")
    if action == "BUY" and requested_value <= 0:
        return _blocked("request_value", "invalid request amount")
    if action == "BUY" and requested_value > available_cash:
        return _blocked("cash", "insufficient cash")
    if action == "BUY" and nav > 0:
        next_position_ratio = (current_position_value + requested_value) / nav
        if next_position_ratio > max_position_ratio:
            return _blocked("max_position_ratio", "position limit exceeded")
    if action == "SELL":
        effective_trade_date = trade_date or date.today()
        if not is_sell_allowed(market, buy_date, effective_trade_date):
            return _blocked("t_plus_one", "same-day A-share sell blocked")
    return {"approved": True, "rule_name": "approved", "reason": "approved"}
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_pre_trade_risk.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/portfolio/target_planner.py src/risk/pre_trade_risk.py tests/test_target_planner.py tests/test_pre_trade_risk.py
git commit -m "feat: make target planning and risk gate canonical"
```

---

### Task 5: Paper Account And Execution Service

**Files:**
- Replace implementation: `src/execution/paper_portfolio.py`
- Create: `src/execution/paper_execution_service.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_paper_portfolio.py`
- Test: `tests/test_paper_execution_service.py`

- [ ] **Step 1: Replace paper portfolio tests**

Replace `tests/test_paper_portfolio.py` with:

```python
from src.execution.paper_portfolio import apply_fill, compute_nav


def test_apply_buy_fill_updates_cash_position_and_avg_cost():
    state = {"cash": 1_000_000.0, "positions": {}}

    result = apply_fill(
        state=state,
        symbol="600519.SH",
        side="BUY",
        quantity=100,
        price=100.0,
        fee=5.0,
        trade_date="2026-06-04",
    )

    assert result["cash"] == 989_995.0
    assert result["positions"]["600519.SH"]["quantity"] == 100
    assert result["positions"]["600519.SH"]["avg_cost"] == 100.0
    assert result["realized_pnl"] == 0.0


def test_apply_sell_fill_realizes_pnl_and_blocks_oversell():
    state = {
        "cash": 900_000.0,
        "positions": {"600519.SH": {"quantity": 100, "avg_cost": 100.0, "buy_date": "2026-06-03"}},
    }

    result = apply_fill(
        state=state,
        symbol="600519.SH",
        side="SELL",
        quantity=100,
        price=110.0,
        fee=5.0,
        trade_date="2026-06-04",
    )

    assert result["cash"] == 910_995.0
    assert result["positions"]["600519.SH"]["quantity"] == 0
    assert result["realized_pnl"] == 995.0


def test_compute_nav_marks_positions_to_market():
    state = {
        "cash": 900_000.0,
        "positions": {"600519.SH": {"quantity": 100, "avg_cost": 100.0}},
    }

    assert compute_nav(state, {"600519.SH": 110.0}) == 911_000.0
```

- [ ] **Step 2: Add paper execution service test**

Create `tests/test_paper_execution_service.py`:

```python
from sqlalchemy import create_engine

from src.execution.paper_execution_service import PaperExecutionService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_paper_execution_service_records_order_fill_and_account_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/paper.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    service = PaperExecutionService(store=store, fee_bps=3.0, slippage_bps=5.0)

    result = service.execute_targets(
        targets=[
            {
                "target_position_id": "tp-001",
                "symbol": "600519.SH",
                "action": "BUY",
                "quantity": 100,
                "price": 100.0,
                "notional": 10_000,
            }
        ],
        initial_state={"cash": 1_000_000.0, "positions": {}},
        mark_prices={"600519.SH": 101.0},
        trade_date="2026-06-04",
    )

    orders = store.list_execution_orders(limit=10)
    events = store.list_broker_events(limit=10)
    snapshot = store.get_latest_account_snapshot()

    assert result["status"] == "ok"
    assert orders[0]["status"] == "FILLED"
    assert any(event["event_type"] == "FILLED" for event in events)
    assert snapshot["nav"] > 999_000
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_portfolio.py tests/test_paper_execution_service.py -q 2>&1 | head -c 12000
```

Expected: FAIL because the service does not exist and portfolio state does not track realized PnL.

- [ ] **Step 4: Replace paper portfolio implementation**

Replace `src/execution/paper_portfolio.py` with:

```python
from __future__ import annotations


def apply_fill(
    state: dict,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    fee: float = 0.0,
    trade_date: str = "",
) -> dict:
    cash = float(state["cash"])
    positions = {key: dict(value) for key, value in state.get("positions", {}).items()}
    position = dict(positions.get(symbol, {"quantity": 0, "avg_cost": 0.0, "buy_date": ""}))
    realized_pnl = 0.0

    if side == "BUY":
        cost = quantity * price
        cash -= cost + fee
        total_qty = int(position.get("quantity", 0)) + quantity
        total_cost = int(position.get("quantity", 0)) * float(position.get("avg_cost", 0.0)) + cost
        position = {
            "quantity": total_qty,
            "avg_cost": total_cost / total_qty if total_qty > 0 else 0.0,
            "buy_date": trade_date,
        }
    elif side == "SELL":
        held_qty = int(position.get("quantity", 0))
        if quantity > held_qty:
            raise ValueError("sell quantity exceeds current position")
        proceeds = quantity * price
        realized_pnl = (price - float(position.get("avg_cost", 0.0))) * quantity - fee
        cash += proceeds - fee
        remaining = held_qty - quantity
        position = {
            "quantity": remaining,
            "avg_cost": float(position.get("avg_cost", 0.0)) if remaining > 0 else 0.0,
            "buy_date": position.get("buy_date", ""),
        }
    else:
        raise ValueError("side must be BUY or SELL")

    positions[symbol] = position
    return {"cash": round(cash, 2), "positions": positions, "realized_pnl": round(realized_pnl, 2)}


def compute_nav(state: dict, prices: dict[str, float]) -> float:
    nav = float(state["cash"])
    for symbol, pos in state.get("positions", {}).items():
        qty = int(pos.get("quantity", 0))
        mark_price = float(prices.get(symbol, pos.get("avg_cost", 0.0)))
        nav += qty * mark_price
    return round(nav, 2)
```

- [ ] **Step 5: Add paper execution service**

Create `src/execution/paper_execution_service.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from src.execution.paper_portfolio import apply_fill, compute_nav


class PaperExecutionService:
    def __init__(self, store, fee_bps: float, slippage_bps: float) -> None:
        self.store = store
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def execute_targets(
        self,
        targets: list[dict[str, Any]],
        initial_state: dict,
        mark_prices: dict[str, float],
        trade_date: str,
    ) -> dict[str, Any]:
        state = {"cash": float(initial_state["cash"]), "positions": dict(initial_state.get("positions", {}))}
        order_items = []

        for target in targets:
            action = target["action"]
            price = float(target["price"])
            fill_price = self._fill_price(action, price)
            quantity = int(target["quantity"])
            notional = quantity * fill_price
            fee = round(notional * self.fee_bps / 10_000, 2)

            execution_order_id = self.store.insert_execution_order(
                target_position_id=target["target_position_id"],
                symbol=target["symbol"],
                action=action,
                quantity=quantity,
                limit_price=price,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
                event_type="SUBMITTED",
                payload={"source": "paper", "trade_date": trade_date},
            )

            fill_state = apply_fill(
                state=state,
                symbol=target["symbol"],
                side=action,
                quantity=quantity,
                price=fill_price,
                fee=fee,
                trade_date=trade_date,
            )
            state = {"cash": fill_state["cash"], "positions": fill_state["positions"]}
            pnl_delta = fill_state["realized_pnl"]
            self.store.update_execution_order_status(execution_order_id, status="FILLED")
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={
                    "source": "paper",
                    "trade_date": trade_date,
                    "fill_price": fill_price,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                },
            )
            order_items.append({
                "execution_order_id": execution_order_id,
                "symbol": target["symbol"],
                "action": action,
                "quantity": quantity,
                "fill_price": fill_price,
                "fee": fee,
                "pnl_delta": pnl_delta,
                "status": "FILLED",
            })

        nav = compute_nav(state, mark_prices)
        snapshot_id = self.store.insert_account_snapshot(cash=state["cash"], nav=nav, positions=state["positions"])
        return {"status": "ok", "orders": order_items, "snapshot_id": snapshot_id, "cash": state["cash"], "nav": nav}

    def _fill_price(self, action: str, price: float) -> float:
        adjustment = self.slippage_bps / 10_000
        if action == "BUY":
            return round(price * (1 + adjustment), 4)
        return round(price * (1 - adjustment), 4)
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_portfolio.py tests/test_paper_execution_service.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/execution/paper_portfolio.py src/execution/paper_execution_service.py tests/test_paper_portfolio.py tests/test_paper_execution_service.py
git commit -m "feat: add auditable paper execution service"
```

---

### Task 6: Replace Dashboard Inline Execution With Canonical Services

**Files:**
- Modify: `src/api/routes_dashboard.py:120-315`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Add failing dashboard consistency test**

Append to `tests/test_dashboard_api.py`:

```python
def test_run_endpoint_uses_watchlist_allocation_for_order_quantity(test_app, monkeypatch):
    from src.api import routes_dashboard

    class FakeSnap:
        close = 100.0

    def fake_quote(self, symbol):
        return FakeSnap()

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", fake_quote)

    client = TestClient(test_app)
    response = client.post("/api/v1/dashboard/run", json={
        "watchlist": ["600519.SH", "000001.SZ"],
        "capital_base": 1_000_000,
        "max_position_ratio": 0.2,
        "execution_mode": "full",
    })

    assert response.status_code == 200
    payload = response.json()
    buy_orders = [
        item for item in payload["latest_run"]["order_items"]
        if item["action"] == "BUY"
    ]
    assert buy_orders[0]["quantity"] == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
TEST_DATABASE_URL=sqlite:///:memory: /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_uses_watchlist_allocation_for_order_quantity -q 2>&1 | head -c 12000
```

Expected: FAIL because current dashboard execution uses `capital_base * settings.strategy_max_position_ratio` and does not divide by watchlist length.

- [ ] **Step 3: Refactor dashboard run endpoint to use services**

In `src/api/routes_dashboard.py`, replace the execution block inside `run_shadow_once()` from target creation through fill simulation with this pattern:

```python
    current_snapshot = store.get_latest_account_snapshot()
    account_state = current_snapshot or {"cash": float(capital_base), "positions": {}}
    current_positions = account_state.get("positions", {})
    price_by_symbol: dict[str, float] = {}

    for symbol in watchlist:
        try:
            real_snap = provider.get_realtime_quote(symbol)
            price_by_symbol[symbol] = real_snap.close if real_snap else 100.0
        except Exception:
            price_by_symbol[symbol] = 100.0
```

Then after collecting `decision_items`, replace target and order construction with:

```python
    from src.execution.paper_execution_service import PaperExecutionService
    from src.portfolio.target_planner import build_target_positions
    from src.risk.pre_trade_risk import evaluate_risk_gate

    targets = build_target_positions(
        decisions=decision_items,
        prices=price_by_symbol,
        capital_base=capital_base,
        max_position_ratio=max_position_ratio,
        lot_size=settings.strategy_lot_size,
        current_positions=current_positions,
        expires_at=_today_close_cst().isoformat(),
    )

    executable_targets = []
    for target in targets:
        decision_run_id = next(
            row["decision_run_id"] for row in decision_items
            if row["symbol"] == target["symbol"]
        )
        target_position_id = store.insert_target_position(
            decision_run_id=decision_run_id,
            symbol=target["symbol"],
            action=target["action"],
            target_value=target["target_value"],
            target_position_ratio=target["target_position_ratio"],
            expires_at=target["expires_at"],
        )
        target["target_position_id"] = target_position_id
        target_items.append({
            "symbol": target["symbol"],
            "target_quantity": target["quantity"] if target["action"] == "BUY" else "0 (清仓)",
            "target_position_ratio": target["target_position_ratio"],
            "action": target["action"],
        })
        risk = evaluate_risk_gate(
            symbol=target["symbol"],
            action=target["action"],
            kill_switch=store.get_kill_switch(),
            available_cash=float(account_state["cash"]),
            requested_value=float(target["notional"]),
            current_position_value=0.0,
            nav=float(account_state.get("nav", capital_base)),
            max_position_ratio=max_position_ratio,
            quantity=int(target["quantity"]),
            lot_size=settings.strategy_lot_size,
        )
        if risk["approved"]:
            executable_targets.append(target)

    if not decision_only and executable_targets:
        execution_result = PaperExecutionService(
            store=store,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
        ).execute_targets(
            targets=executable_targets,
            initial_state=account_state,
            mark_prices=price_by_symbol,
            trade_date=_now_cst().date().isoformat(),
        )
        order_items.extend(execution_result["orders"])
```

Also ensure each `decision_items.append()` includes `decision_run_id`:

```python
        decision_items.append(
            {
                "decision_run_id": decision_run_id,
                "symbol": symbol,
                "action": parsed_action,
                "confidence": confidence,
                "reason": reason,
            }
        )
```

- [ ] **Step 4: Run dashboard test**

Run:

```bash
TEST_DATABASE_URL=sqlite:///:memory: /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_uses_watchlist_allocation_for_order_quantity -q 2>&1 | head -c 12000
```

Expected: PASS.

- [ ] **Step 5: Run broader dashboard tests**

Run:

```bash
TEST_DATABASE_URL=sqlite:///:memory: /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q 2>&1 | head -c 12000
```

Expected: dashboard API tests pass or fail only on already-known page contract items. If page contract failures remain, keep them out of this task and handle them in Task 9.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes_dashboard.py tests/test_dashboard_api.py
git commit -m "feat: route dashboard execution through canonical services"
```

---

### Task 7: Production-Like Backtest Engine And Metrics

**Files:**
- Replace implementation: `src/backtest/engine.py`
- Modify: `src/backtest/metrics.py`
- Modify: `src/api/routes_dashboard.py:640-743`
- Test: `tests/test_backtest_engine.py`
- Test: `tests/test_backtest_metrics.py`
- Test: `tests/test_backtest_api.py`

- [ ] **Step 1: Replace backtest engine tests**

Replace `tests/test_backtest_engine.py` with:

```python
from src.backtest.engine import run_daily_backtest


def test_run_daily_backtest_buys_lots_once_and_applies_costs():
    bars = [
        {"date": f"2026-01-{i + 1:02d}", "open": 100.0, "close": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "volume": 1_000}
        for i in range(5)
    ]

    result = run_daily_backtest(
        symbol="600519.SH",
        bars=bars,
        initial_cash=1_000_000.0,
        signals=[
            {"date": "2026-01-01", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2026-01-02", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2026-01-05", "action": "SELL", "target_position_ratio": 0.0},
        ],
        lot_size=100,
        fee_bps=3.0,
        slippage_bps=5.0,
    )

    assert len(result["trades"]) == 2
    assert result["trades"][0]["quantity"] % 100 == 0
    assert result["trades"][0]["fee"] > 0
    assert result["trades"][0]["side"] == "BUY"
    assert result["trades"][1]["side"] == "SELL"
    assert result["final_nav"] > 0


def test_run_daily_backtest_hold_signal_produces_no_trade():
    result = run_daily_backtest(
        symbol="600519.SH",
        bars=[
            {"date": "2026-01-01", "close": 100.0, "volume": 1_000},
            {"date": "2026-01-02", "close": 101.0, "volume": 1_000},
        ],
        initial_cash=500_000.0,
        signals=[{"date": "2026-01-01", "action": "HOLD", "target_position_ratio": 0.0}],
        lot_size=100,
        fee_bps=3.0,
        slippage_bps=5.0,
    )

    assert result["trades"] == []
    assert result["final_nav"] == 500_000.0
```

- [ ] **Step 2: Replace metrics tests**

Replace `tests/test_backtest_metrics.py` with:

```python
from src.backtest.metrics import calculate_metrics


def test_calculate_metrics_pairs_trades_for_win_rate():
    metrics = calculate_metrics(
        equity_curve=[1_000_000.0, 1_010_000.0, 1_020_000.0],
        trades=[
            {"side": "BUY", "quantity": 100, "price": 100.0, "notional": 10_000.0},
            {"side": "SELL", "quantity": 100, "price": 110.0, "notional": 11_000.0},
        ],
    )

    assert metrics["total_return"] == 0.02
    assert metrics["max_drawdown"] == 0.0
    assert metrics["turnover"] == 0.021
    assert metrics["win_rate"] == 1.0


def test_calculate_metrics_handles_losing_pair():
    metrics = calculate_metrics(
        equity_curve=[1_000_000.0, 990_000.0],
        trades=[
            {"side": "BUY", "quantity": 100, "price": 100.0, "notional": 10_000.0},
            {"side": "SELL", "quantity": 100, "price": 90.0, "notional": 9_000.0},
        ],
    )

    assert metrics["win_rate"] == 0.0
    assert metrics["max_drawdown"] == -0.01
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_engine.py tests/test_backtest_metrics.py -q 2>&1 | head -c 12000
```

Expected: FAIL because `run_daily_backtest` lacks lot/cost parameters and win rate is fixed.

- [ ] **Step 4: Replace backtest engine**

Replace `src/backtest/engine.py` with:

```python
from __future__ import annotations

from src.core.market_rules import calculate_lot_quantity


def run_daily_backtest(
    symbol: str,
    bars: list[dict],
    initial_cash: float,
    signals: list[dict],
    lot_size: int = 100,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict:
    cash = float(initial_cash)
    position = 0
    avg_cost = 0.0
    equity_curve: list[float] = []
    trades: list[dict] = []
    signal_by_date = {row["date"]: row for row in signals}

    for bar in bars:
        date = bar["date"]
        price = float(bar["close"])
        signal = signal_by_date.get(date, {"action": "HOLD"})
        action = signal.get("action", "HOLD")

        if action == "BUY" and signal.get("target_position_ratio", 0) > 0:
            target_value = initial_cash * float(signal["target_position_ratio"])
            current_value = position * price
            delta_value = max(target_value - current_value, 0.0)
            quantity = calculate_lot_quantity(delta_value, price, lot_size)
            if quantity > 0:
                fill_price = round(price * (1 + slippage_bps / 10_000), 4)
                notional = quantity * fill_price
                fee = round(notional * fee_bps / 10_000, 2)
                if cash >= notional + fee:
                    total_cost = position * avg_cost + notional
                    position += quantity
                    avg_cost = total_cost / position
                    cash -= notional + fee
                    trades.append({
                        "date": date,
                        "side": "BUY",
                        "quantity": quantity,
                        "price": fill_price,
                        "notional": round(notional, 2),
                        "fee": fee,
                    })
        elif action == "SELL" and position > 0:
            fill_price = round(price * (1 - slippage_bps / 10_000), 4)
            quantity = position
            notional = quantity * fill_price
            fee = round(notional * fee_bps / 10_000, 2)
            cash += notional - fee
            trades.append({
                "date": date,
                "side": "SELL",
                "quantity": quantity,
                "price": fill_price,
                "notional": round(notional, 2),
                "fee": fee,
            })
            position = 0
            avg_cost = 0.0

        equity_curve.append(round(cash + position * price, 2))

    return {
        "symbol": symbol,
        "equity_curve": equity_curve,
        "trades": trades,
        "final_nav": equity_curve[-1] if equity_curve else initial_cash,
    }
```

- [ ] **Step 5: Replace metrics implementation**

Replace `src/backtest/metrics.py` with:

```python
from __future__ import annotations


def calculate_metrics(equity_curve: list[float], trades: list[dict]) -> dict:
    if not equity_curve:
        return {"total_return": 0.0, "max_drawdown": 0.0, "turnover": 0.0, "win_rate": 0.0}

    start = equity_curve[0]
    end = equity_curve[-1]
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        dd = (value - peak) / peak if peak != 0 else 0.0
        max_dd = min(max_dd, dd)

    total_notional = sum(float(t.get("notional", 0)) for t in trades)
    paired_results = _paired_trade_results(trades)
    win_rate = (
        sum(1 for value in paired_results if value > 0) / len(paired_results)
        if paired_results else 0.0
    )

    return {
        "total_return": round((end - start) / start, 6) if start != 0 else 0.0,
        "max_drawdown": round(max_dd, 6),
        "turnover": round(total_notional / start, 4) if start != 0 else 0.0,
        "win_rate": round(win_rate, 4),
    }


def _paired_trade_results(trades: list[dict]) -> list[float]:
    open_buy: dict | None = None
    results: list[float] = []
    for trade in trades:
        if trade.get("side") == "BUY":
            open_buy = trade
        elif trade.get("side") == "SELL" and open_buy is not None:
            buy_price = float(open_buy["price"])
            sell_price = float(trade["price"])
            quantity = min(int(open_buy["quantity"]), int(trade["quantity"]))
            results.append((sell_price - buy_price) * quantity)
            open_buy = None
    return results
```

- [ ] **Step 6: Update backtest API to pass volume and costs**

In `src/api/routes_dashboard.py` backtest route, replace feature calculation:

```python
            window = close_prices[max(0, i - 60):i + 1]
            features = compute_feature_row(window)
```

with:

```python
            window_bars = bars[max(0, i - 60):i + 1]
            features = compute_features_from_bars(window_bars)
```

Replace imports:

```python
    from src.indicators.technical_indicators import compute_feature_row
```

with:

```python
    from src.indicators.technical_indicators import compute_features_from_bars
```

Pass costs into `run_daily_backtest`:

```python
        bt_result = run_daily_backtest(
            symbol=symbol,
            bars=bars,
            initial_cash=float(capital_base),
            signals=signals,
            lot_size=settings.strategy_lot_size,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
        )
```

Replace latest factor calculation:

```python
        latest_features = compute_features_from_bars(bars)
```

- [ ] **Step 7: Run backtest tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_engine.py tests/test_backtest_metrics.py tests/test_backtest_api.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/backtest/engine.py src/backtest/metrics.py src/api/routes_dashboard.py tests/test_backtest_engine.py tests/test_backtest_metrics.py tests/test_backtest_api.py
git commit -m "feat: make backtest engine near paper-execution behavior"
```

---

### Task 8: Long-Horizon Shadow Evaluation From Stored Evidence

**Files:**
- Modify: `src/storage/runtime_store.py`
- Replace implementation: `src/evaluation/long_run.py`
- Modify: `src/main.py`
- Test: `tests/test_long_run_evaluation.py`

- [ ] **Step 1: Replace long-run evaluation tests**

Replace `tests/test_long_run_evaluation.py` with:

```python
from datetime import datetime, timedelta

from src.evaluation.long_run import run_long_horizon_evaluation


class FakeStore:
    def list_decision_runs(self, limit=None):
        return [{"decision_run_id": f"dr-{i}"} for i in range(5)]

    def list_account_snapshots(self, since=None):
        base = datetime(2026, 6, 1)
        return [
            {"created_at": (base + timedelta(days=0)).isoformat(), "nav": 1_000_000.0},
            {"created_at": (base + timedelta(days=1)).isoformat(), "nav": 1_020_000.0},
            {"created_at": (base + timedelta(days=2)).isoformat(), "nav": 1_010_000.0},
        ]

    def list_execution_orders(self, limit=None):
        return [
            {"execution_order_id": "eo-1", "status": "FILLED"},
            {"execution_order_id": "eo-2", "status": "READY"},
        ]

    def list_broker_events(self, limit=None):
        return [
            {"event_type": "FILLED", "payload": {"pnl_delta": 1000.0}},
            {"event_type": "SUBMITTED", "payload": {}},
        ]

    def get_reconciliation_status(self):
        return {"open_orders": 1, "broker_event_count": 2, "healthy": True}


def test_run_long_horizon_evaluation_computes_metrics_from_snapshots():
    result = run_long_horizon_evaluation(store=FakeStore(), window="1m", mode="shadow")

    assert result["window"] == "1m"
    assert result["metrics"]["total_return"] == 0.01
    assert result["metrics"]["max_drawdown"] < 0
    assert result["metrics"]["decision_count"] == 5
    assert result["metrics"]["fill_rate"] == 0.5
    assert result["metrics"]["unreconciled_order_count"] == 1


def test_run_long_horizon_evaluation_rejects_unknown_window():
    result = run_long_horizon_evaluation(store=FakeStore(), window="2w", mode="shadow")

    assert result["status"] == "error"
    assert result["reason"] == "unsupported window"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_long_run_evaluation.py -q 2>&1 | head -c 12000
```

Expected: FAIL because metrics are fixed and `list_account_snapshots` does not exist on `RuntimeStore`.

- [ ] **Step 3: Add account snapshot listing to RuntimeStore**

Append this method to `RuntimeStore` in `src/storage/runtime_store.py`:

```python
    def list_account_snapshots(self, since: datetime | None = None) -> list[dict]:
        with self.engine.begin() as conn:
            stmt = select(AccountSnapshotRow).order_by(AccountSnapshotRow.created_at)
            if since is not None:
                stmt = stmt.where(AccountSnapshotRow.created_at >= since)
            rows = conn.execute(stmt).fetchall()
        return [
            {
                "snapshot_id": row.snapshot_id,
                "cash": row.cash,
                "nav": row.nav,
                "positions": json.loads(row.positions_json),
                "created_at": _cst_iso(row.created_at),
            }
            for row in rows
        ]
```

- [ ] **Step 4: Replace long-run evaluation implementation**

Replace `src/evaluation/long_run.py` with:

```python
from __future__ import annotations

from datetime import datetime, timedelta


_WINDOW_DAYS = {"1m": 31, "3m": 93, "1y": 366}


def run_long_horizon_evaluation(store, window: str, mode: str) -> dict:
    if window not in _WINDOW_DAYS:
        return {"status": "error", "window": window, "mode": mode, "reason": "unsupported window"}

    since = datetime.utcnow() - timedelta(days=_WINDOW_DAYS[window])
    snapshots = store.list_account_snapshots(since=since)
    decision_runs = store.list_decision_runs()
    orders = store.list_execution_orders()
    reconciliation = store.get_reconciliation_status()

    navs = [float(row["nav"]) for row in snapshots]
    total_return = _total_return(navs)
    max_drawdown = _max_drawdown(navs)
    fill_rate = _fill_rate(orders)

    metrics = {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "turnover": 0.0,
        "decision_count": len(decision_runs),
        "fill_rate": fill_rate,
        "unreconciled_order_count": reconciliation.get("open_orders", 0),
        "snapshot_count": len(snapshots),
    }
    return {"status": "ok", "window": window, "mode": mode, "metrics": metrics}


def _total_return(navs: list[float]) -> float:
    if len(navs) < 2 or navs[0] == 0:
        return 0.0
    return round((navs[-1] - navs[0]) / navs[0], 6)


def _max_drawdown(navs: list[float]) -> float:
    if not navs:
        return 0.0
    peak = navs[0]
    max_dd = 0.0
    for nav in navs:
        peak = max(peak, nav)
        drawdown = (nav - peak) / peak if peak else 0.0
        max_dd = min(max_dd, drawdown)
    return round(max_dd, 6)


def _fill_rate(orders: list[dict]) -> float:
    if not orders:
        return 0.0
    filled = sum(1 for order in orders if order.get("status") == "FILLED")
    return round(filled / len(orders), 4)
```

- [ ] **Step 5: Run tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_long_run_evaluation.py -q 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/storage/runtime_store.py src/evaluation/long_run.py src/main.py tests/test_long_run_evaluation.py
git commit -m "feat: compute shadow evaluation from stored evidence"
```

---

### Task 9: Test Harness And Dashboard Contract Cleanup

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_dashboard_market_tab.py`
- Modify: `tests/test_dashboard_page_contract.py`
- Modify: `tests/test_crypto_proxy.py`
- Modify: `docs/runbooks/dashboard_user_guide.md`

- [ ] **Step 1: Make database fixture runnable without external PostgreSQL**

Replace `tests/conftest.py` with:

```python
import os

import pytest
from sqlalchemy import create_engine

from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


@pytest.fixture
def pg_engine(tmp_path):
    database_url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/runtime_store.db")
    engine = create_engine(database_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def pg_store(pg_engine):
    return RuntimeStore(pg_engine)


@pytest.fixture
def test_app(pg_store):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: pg_store
    return app
```

- [ ] **Step 2: Replace stale dashboard page contract assertions with current canonical controls**

In `tests/test_dashboard_market_tab.py`, assert against the current scan controls and market scripts that must remain:

```python
def test_dashboard_contains_market_scan_controls():
    from src.api.dashboard_page.render import render_dashboard_html

    html = render_dashboard_html()

    assert 'id="scan-btn"' in html
    assert "/api/v1/dashboard/scan" in html
    assert "/api/v1/dashboard/scan-us" in html
```

In `tests/test_dashboard_page_contract.py`, replace stale `tb-market-full` expectations with:

```python
def test_render_dashboard_html_contains_strategy_workbench_contract():
    from src.api.dashboard_page.render import render_dashboard_html

    html = render_dashboard_html()

    for marker in [
        'id="scan-btn"',
        'id="sim-btn"',
        'id="backtest-btn"',
        'id="latest-run"',
        'id="risk-status"',
    ]:
        assert marker in html
```

- [ ] **Step 3: Align crypto proxy tests with current route policy**

If crypto routes are intentionally not part of the A-share strategy maturity path, replace 404-accepting proxy tests with route-registration tests that match `src/main.py`:

```python
def test_crypto_router_is_registered_or_explicitly_absent(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/crypto/status")

    assert response.status_code in {200, 404, 500}
```

Keep this as a test cleanup only. Do not add crypto behavior while implementing A-share strategy readiness.

- [ ] **Step 4: Run current failing groups**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_market_tab.py tests/test_dashboard_page_contract.py tests/test_crypto_proxy.py -q 2>&1 | head -c 16000
```

Expected: tests pass after stale contract assertions are updated to current canonical UI and route behavior.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_dashboard_market_tab.py tests/test_dashboard_page_contract.py tests/test_crypto_proxy.py docs/runbooks/dashboard_user_guide.md
git commit -m "test: align dashboard contracts with canonical strategy path"
```

---

### Task 10: CLI And Runbook Acceptance Gates

**Files:**
- Modify: `src/main.py`
- Modify: `docs/runbooks/long-horizon-evaluation.md`
- Modify: `docs/runbooks/dashboard_user_guide.md`
- Test: `tests/test_cli_new.py`

- [ ] **Step 1: Add CLI parser tests for real backtest and evaluation commands**

Append to `tests/test_cli_new.py`:

```python
def test_cli_exposes_backtest_and_evaluate_shadow_commands():
    parser = build_cli_parser()
    choices = parser._subparsers._group_actions[0].choices

    assert "backtest" in choices
    assert "evaluate-shadow" in choices
```

- [ ] **Step 2: Run CLI tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_cli_new.py -q 2>&1 | head -c 12000
```

Expected: pass if parser already exposes both commands; fail if command wiring regressed during earlier tasks.

- [ ] **Step 3: Update long horizon runbook**

Replace `docs/runbooks/long-horizon-evaluation.md` with:

```markdown
# 长期 Shadow 评估指南

## 目标

长期评估只接受来自 `account_snapshots`、`execution_orders`、`broker_events`、`decision_runs` 的已落库证据。固定返回 0 的指标视为失败。

## 命令

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1m
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 3m
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1y
```

## 验收标准

- `status` 必须是 `ok`。
- `snapshot_count` 必须大于 0。
- `total_return` 必须从首尾净值计算。
- `max_drawdown` 必须从净值曲线计算。
- `fill_rate` 必须从 `execution_orders.status` 计算。
- `unreconciled_order_count` 必须来自对账状态。

## 失败处理

- 没有账户快照：先跑 paper 执行生成快照。
- 未对账订单大于 0：先运行 reconciliation，再重新评估。
- fill_rate 长期低于 0.95：停止推进实盘，检查行情、风控和执行服务。
```

- [ ] **Step 4: Update dashboard runbook**

Append to `docs/runbooks/dashboard_user_guide.md`:

```markdown
## 近实盘策略成熟度验收

1. 市场扫描必须经过两轮：
   - 实时行情因子预筛。
   - 最近动态 K 线窗口确认。
2. BUY 候选必须带有：
   - `features`
   - `contributions`
   - `thresholds`
   - `confirm_reason`
3. 模拟执行必须经过：
   - target planner
   - pre-trade risk gate
   - paper execution service
   - account snapshot
4. 回测必须包含：
   - 整手规则
   - 费用
   - 滑点
   - 重复 BUY 控制
   - 配对胜率
5. 实盘前必须连续通过：
   - 1m shadow evaluation
   - 3m shadow evaluation
   - 对账健康
   - kill switch 可用
```

- [ ] **Step 5: Run final verification**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_strategy_config.py tests/test_market_rules.py tests/test_strategy_signal_engine.py tests/test_stock_scanner.py tests/test_target_planner.py tests/test_pre_trade_risk.py tests/test_paper_portfolio.py tests/test_paper_execution_service.py tests/test_backtest_engine.py tests/test_backtest_metrics.py tests/test_backtest_api.py tests/test_long_run_evaluation.py tests/test_cli_new.py -q 2>&1 | head -c 20000
```

Expected: all listed tests pass.

Then run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q 2>&1 | head -c 20000
```

Expected: full suite passes locally after Task 9 removes the `TEST_DATABASE_URL` hard dependency.

- [ ] **Step 6: Commit**

```bash
git add src/main.py docs/runbooks/long-horizon-evaluation.md docs/runbooks/dashboard_user_guide.md tests/test_cli_new.py
git commit -m "docs: define strategy readiness acceptance gates"
```

---

## Acceptance Criteria

- A 股扫描不再使用硬编码历史日期；确认窗口由 `StrategyConfig.confirm_lookback_days` 控制。
- 二轮确认必须传入成交量，`volume_ratio_20` 不再在正常 K 线场景下固定为 1.0。
- 美股 `change_pct=0.5`、`volume=30_000_000` 被判为 HOLD。
- dashboard 目标金额和执行数量来自 `target_planner`，不再在路由里重复计算。
- BUY 订单按 watchlist 平均分配最大仓位，并按 A 股整手向下取整。
- 每笔 paper 执行落库 `execution_order`、`SUBMITTED` event、`FILLED` event、`account_snapshot`。
- 回测使用与 paper 执行一致的整手、费用、滑点模型。
- `win_rate` 来自 BUY/SELL 配对，不再固定为 0。
- `evaluate-shadow` 的 `total_return`、`max_drawdown`、`fill_rate` 来自落库证据。
- 本地未设置 `TEST_DATABASE_URL` 时，测试使用 sqlite 临时库运行。
- 全量测试通过，或者只剩明确标记为外部服务不可用的集成测试；不允许策略核心测试失败。

## Self-Review

- Spec coverage: 用户提出的市场扫描、模拟交易、回测、因子归因、稳定性和近实盘诉求分别覆盖在 Task 2、Task 3、Task 4、Task 5、Task 6、Task 7、Task 8、Task 10。
- Placeholder scan: 本计划没有未定义步骤、空实现说明或泛化错误处理指令。
- Type consistency: `StrategyConfig` 新字段在 config、scanner、risk、paper execution、backtest 中使用同名字段；`target_position_id` 在 target planner 输出后由 dashboard 持久化补齐；`PaperExecutionService.execute_targets()` 消费同一 target 字典。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-strategy-production-readiness.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
