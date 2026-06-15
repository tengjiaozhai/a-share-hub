# Market-Aware Lot Sizing And Empty-Order Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard explain when no executable target/order is generated, and stop applying A-share 100-share lot sizing to US symbols.

**Architecture:** Keep the fix on the existing dashboard run path instead of adding frontend-only heuristics. Split lot sizing at the configuration/core-rule layer, resolve the effective lot size per symbol in backend code, and let the backend emit explicit timeline messages when actionable BUY decisions produce zero executable targets.

**Tech Stack:** FastAPI, plain Python domain services, existing dashboard HTML/JS rendering, pytest

---

## File Structure

- Modify: `src/core/config.py`
  Add separate A-share and US lot-size settings; remove the single shared lot-size setting from the canonical runtime config.
- Modify: `src/strategy/strategy_config.py`
  Keep strategy config aligned with split lot-size settings so config consumers do not drift.
- Modify: `src/core/market_rules.py`
  Add market inference and lot-size resolution helpers next to the existing lot-size math.
- Modify: `src/portfolio/target_planner.py`
  Resolve the effective lot size per symbol before quantity rounding; surface the resolved lot size on each target for downstream risk/timeline use.
- Modify: `src/api/routes_dashboard.py`
  Use market-aware lot sizing in both `/api/v1/dashboard/run` and `/api/v1/dashboard/backtest`; emit explicit no-executable-order messages in the timeline.
- Modify: `tests/test_market_rules.py`
  Add regression coverage for symbol-to-market inference and split lot-size resolution.
- Modify: `tests/test_strategy_config.py`
  Update config assertions to the new `lot_size_a` / `lot_size_us` fields.
- Modify: `tests/test_target_planner.py`
  Add target-planner coverage for US single-share rounding and resolved lot-size propagation.
- Modify: `tests/test_dashboard_api.py`
  Add regression coverage for the zero-target timeline message and the US-symbol full-run path that should produce executable orders.
- Modify: `tests/test_backtest_api.py`
  Add a focused regression that the dashboard backtest route passes US lot size `1` instead of `100`.
- Modify: `docs/sop.md`
  Update the beginner-facing wording so the page behavior matches the new backend feedback.

---

### Task 1: Split Runtime Lot-Size Configuration And Core Resolution

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/strategy/strategy_config.py`
- Modify: `src/core/market_rules.py`
- Test: `tests/test_market_rules.py`
- Test: `tests/test_strategy_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_market_rules.py
from src.core.market_rules import (
    calculate_lot_quantity,
    infer_market_from_symbol,
    is_limit_locked,
    is_sell_allowed,
    is_valid_lot_quantity,
    resolve_lot_size,
)


def test_infer_market_from_symbol_distinguishes_a_share_and_us():
    assert infer_market_from_symbol("600519.SH") == "CN_A"
    assert infer_market_from_symbol("000858.SZ") == "CN_A"
    assert infer_market_from_symbol("AAPL") == "US"
    assert infer_market_from_symbol("NVDA.US") == "US"


def test_resolve_lot_size_uses_split_market_settings():
    assert resolve_lot_size(symbol="600519.SH", lot_size_a=100, lot_size_us=1) == 100
    assert resolve_lot_size(symbol="AAPL", lot_size_a=100, lot_size_us=1) == 1
```

```python
# tests/test_strategy_config.py
from src.core.config import Settings
from src.strategy.strategy_config import StrategyConfig


def test_strategy_config_exposes_split_lot_size_fields():
    settings = Settings(
        strategy_top_n=10,
        strategy_max_position_ratio=0.2,
        strategy_buy_score_threshold=0.55,
        strategy_sell_score_threshold=-0.20,
        strategy_scan_buy_threshold_a=0.55,
        strategy_scan_buy_threshold_us=0.45,
        strategy_min_confirm_bars=61,
        strategy_confirm_lookback_days=180,
        strategy_lot_size_a=100,
        strategy_lot_size_us=1,
        strategy_fee_bps=3.0,
        strategy_slippage_bps=5.0,
        strategy_max_daily_loss_ratio=0.03,
    )

    config = StrategyConfig.from_settings(settings)

    assert config.lot_size_a == 100
    assert config.lot_size_us == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_rules.py tests/test_strategy_config.py -v
```

Expected:

- `ImportError` or `AttributeError` for `infer_market_from_symbol` / `resolve_lot_size`
- `ValidationError` or `AttributeError` because `strategy_lot_size_a` / `strategy_lot_size_us` do not exist yet

- [ ] **Step 3: Write the minimal implementation**

```python
# src/core/config.py
class Settings(BaseSettings):
    ...
    strategy_lot_size_a: int = 100
    strategy_lot_size_us: int = 1
    strategy_fee_bps: float = 3.0
    strategy_slippage_bps: float = 5.0
```

```python
# src/strategy/strategy_config.py
@dataclass(frozen=True)
class StrategyConfig:
    ...
    lot_size_a: int
    lot_size_us: int
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
            lot_size_a=settings.strategy_lot_size_a,
            lot_size_us=settings.strategy_lot_size_us,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
            max_daily_loss_ratio=settings.strategy_max_daily_loss_ratio,
        )
```

```python
# src/core/market_rules.py
def infer_market_from_symbol(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if normalized.endswith(".SH") or normalized.endswith(".SZ"):
        return "CN_A"
    return "US"


def resolve_lot_size(
    symbol: str,
    lot_size_a: int = 100,
    lot_size_us: int = 1,
    market: str | None = None,
) -> int:
    market_code = (market or infer_market_from_symbol(symbol)).upper()
    if market_code in {"A", "CN_A"}:
        return lot_size_a
    if market_code in {"US", "NASDAQ", "NYSE"}:
        return lot_size_us
    return lot_size_a
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_rules.py tests/test_strategy_config.py -v
```

Expected: PASS for all tests in both files.

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/core/config.py src/strategy/strategy_config.py src/core/market_rules.py tests/test_market_rules.py tests/test_strategy_config.py
git commit -m "feat: split market lot size settings"
```

### Task 2: Apply Market-Aware Lot Sizing To Target Planning And Backtest

**Files:**
- Modify: `src/portfolio/target_planner.py`
- Modify: `src/api/routes_dashboard.py`
- Test: `tests/test_target_planner.py`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_backtest_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_target_planner.py
from src.portfolio.target_planner import build_target_position


def test_build_target_position_uses_single_share_lots_for_us_symbols():
    target = build_target_position(
        symbol="AAPL",
        action="BUY",
        capital_base=10_000,
        max_position_ratio=0.2,
        watchlist_size=5,
        price=150.0,
        lot_size_a=100,
        lot_size_us=1,
    )

    assert target["target_value"] == 400
    assert target["quantity"] == 2
    assert target["notional"] == 300
    assert target["lot_size"] == 1
```

```python
# tests/test_dashboard_api.py
from fastapi.testclient import TestClient


def test_run_endpoint_uses_us_single_share_lot_size(test_app, monkeypatch):
    from src.api import routes_dashboard

    class FakeSnap:
        close = 150.0

    class FakeUSLLM:
        model = "deepseek-v4-pro"

        def generate(self, prompt: str, temperature: float = 0.7) -> str:
            symbol = "AAPL"
            return (
                f'{{"symbol":"{symbol}","action":"BUY","confidence":80,'
                f'"target_position_ratio":0.2,"reason":"real-mode"}}'
            )

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", lambda self, symbol: FakeSnap())
    monkeypatch.setattr(routes_dashboard, "_get_llm", lambda: FakeUSLLM())

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "watchlist": ["AAPL"],
            "capital_base": 10_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "real",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    buy_orders = [item for item in payload["latest_run"]["order_items"] if item["action"] == "BUY"]
    assert buy_orders[0]["quantity"] == 13
```

```python
# tests/test_backtest_api.py
from fastapi.testclient import TestClient
from src.main import build_app


def test_backtest_endpoint_uses_us_single_share_lot_size(monkeypatch):
    from src.api import routes_dashboard
    from src.strategy import signal_engine
    from src.us_stock.yahoo_provider import YahooProvider
    from src.backtest import engine as backtest_engine

    captured = {}

    class FakeKline:
        def __init__(self, day: int):
            from datetime import datetime
            self.timestamp = datetime(2025, 1, day)
            self.open = 100.0
            self.high = 101.0
            self.low = 99.0
            self.close = 100.0
            self.volume = 1000

    def fake_get_kline(self, symbol, interval="1d", range_str="3mo"):
        return [FakeKline(day) for day in range(1, 29)] * 3

    def fake_build_signal(symbol, features, config):
        return {"symbol": symbol, "action": "HOLD", "technical_score": 0.0}

    def fake_run_daily_backtest(symbol, bars, initial_cash, signals, lot_size, fee_bps, slippage_bps):
        captured["lot_size"] = lot_size
        return {"equity_curve": [initial_cash, initial_cash], "trades": [], "final_nav": initial_cash}

    monkeypatch.setattr(YahooProvider, "get_kline", fake_get_kline)
    monkeypatch.setattr(signal_engine, "build_signal", fake_build_signal)
    monkeypatch.setattr(backtest_engine, "run_daily_backtest", fake_run_daily_backtest)

    client = TestClient(build_app())
    response = client.post("/api/v1/dashboard/backtest", json={
        "watchlist": ["AAPL"],
        "market": "us",
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "capital_base": 1000000,
    })

    assert response.status_code == 200
    assert captured["lot_size"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_dashboard_api.py tests/test_backtest_api.py -v
```

Expected:

- US target-planner quantity stays `0` because the code still rounds with `lot_size=100`
- Dashboard run test returns no BUY order or wrong quantity
- Backtest API test captures `lot_size == 100`

- [ ] **Step 3: Write the minimal implementation**

```python
# src/portfolio/target_planner.py
from src.core.market_rules import calculate_lot_quantity, resolve_lot_size


def build_target_position(
    symbol: str,
    action: str,
    capital_base: float,
    max_position_ratio: float,
    watchlist_size: int,
    price: float,
    lot_size_a: int,
    lot_size_us: int,
    current_quantity: int = 0,
    expires_at: str = "",
    market: str | None = None,
) -> dict[str, Any]:
    resolved_lot_size = resolve_lot_size(
        symbol=symbol,
        lot_size_a=lot_size_a,
        lot_size_us=lot_size_us,
        market=market,
    )

    if action == "BUY":
        target_position_ratio = max_position_ratio / watchlist_size
        target_value = int(capital_base * target_position_ratio)
        quantity = calculate_lot_quantity(target_value, price, resolved_lot_size)
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
        "lot_size": resolved_lot_size,
        "expires_at": expires_at,
    }
```

```python
# src/portfolio/target_planner.py
def build_target_positions(
    decisions: list[dict],
    prices: dict[str, float],
    capital_base: float,
    max_position_ratio: float,
    lot_size_a: int,
    lot_size_us: int,
    current_positions: dict[str, dict],
    expires_at: str = "",
    market: str | None = None,
) -> list[dict[str, Any]]:
    ...
        target = build_target_position(
            symbol=symbol,
            action=row["action"],
            capital_base=capital_base,
            max_position_ratio=max_position_ratio,
            watchlist_size=watchlist_size,
            price=prices[symbol],
            lot_size_a=lot_size_a,
            lot_size_us=lot_size_us,
            current_quantity=int(current_position.get("quantity", 0)),
            expires_at=expires_at,
            market=market,
        )
```

```python
# src/api/routes_dashboard.py
from src.core.market_rules import resolve_lot_size

targets = build_target_positions(
    decisions=decision_items,
    prices=price_by_symbol,
    capital_base=capital_base,
    max_position_ratio=max_position_ratio,
    lot_size_a=settings.strategy_lot_size_a,
    lot_size_us=settings.strategy_lot_size_us,
    current_positions=current_positions,
    expires_at=_today_close_cst().isoformat(),
)

...
risk = evaluate_risk_gate(
    symbol=target["symbol"],
    action=target["action"],
    kill_switch=store.get_kill_switch(),
    available_cash=float(account_state["cash"]),
    requested_value=float(target["notional"]),
    current_position_value=current_position_value,
    nav=float(account_state.get("nav", capital_base)),
    max_position_ratio=max_position_ratio,
    quantity=int(target["quantity"]),
    lot_size=int(target["lot_size"]),
)
```

```python
# src/api/routes_dashboard.py
lot_size = resolve_lot_size(
    symbol=symbol,
    lot_size_a=settings.strategy_lot_size_a,
    lot_size_us=settings.strategy_lot_size_us,
    market="US" if market == "us" else "CN_A",
)

bt_result = run_daily_backtest(
    symbol=symbol,
    bars=bars,
    initial_cash=float(capital_base),
    signals=signals,
    lot_size=lot_size,
    fee_bps=settings.strategy_fee_bps,
    slippage_bps=settings.strategy_slippage_bps,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_dashboard_api.py tests/test_backtest_api.py -v
```

Expected:

- US planner test returns quantity `2` and lot size `1`
- Dashboard run creates a BUY order for `AAPL` instead of silently dropping the target
- Backtest route forwards lot size `1` for US symbols

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/portfolio/target_planner.py src/api/routes_dashboard.py tests/test_target_planner.py tests/test_dashboard_api.py tests/test_backtest_api.py
git commit -m "feat: use market-aware lot sizing"
```

### Task 3: Explain Empty Target / Empty Execution On The Dashboard

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Modify: `tests/test_dashboard_api.py`
- Modify: `docs/sop.md`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dashboard_api.py
from fastapi.testclient import TestClient


def test_run_endpoint_explains_zero_executable_orders(test_app, monkeypatch):
    from src.api import routes_dashboard

    class ExpensiveSnap:
        close = 2000.0

    class FakeUSLLM:
        model = "deepseek-v4-pro"

        def generate(self, prompt: str, temperature: float = 0.7) -> str:
            symbol = "AAPL" if "AAPL" in prompt else "MRVL"
            return (
                f'{{"symbol":"{symbol}","action":"BUY","confidence":80,'
                f'"target_position_ratio":0.2,"reason":"real-mode"}}'
            )

    monkeypatch.setattr(routes_dashboard.AkshareProvider, "get_realtime_quote", lambda self, symbol: ExpensiveSnap())
    monkeypatch.setattr(routes_dashboard, "_get_llm", lambda: FakeUSLLM())

    client = TestClient(test_app)
    response = client.post(
        "/api/v1/dashboard/run",
        json={
            "watchlist": ["MRVL", "AAPL"],
            "capital_base": 10_000,
            "max_position_ratio": 0.2,
            "execution_mode": "full",
            "decision_mode": "real",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    steps = payload["latest_run"]["steps"]

    target_done = next(step for step in steps if step["stage"] == "target" and step["status"] == "done")
    execute_done = next(step for step in steps if step["stage"] == "execute" and step["status"] == "done")
    reconcile_done = next(step for step in steps if step["stage"] == "reconcile" and step["status"] == "done")

    assert "资金不足或最小交易单位限制，未生成可执行订单" in (target_done.get("message") or "")
    assert "无可执行订单，已跳过模拟执行" in (execute_done.get("message") or "")
    assert "未发生模拟成交" in (reconcile_done.get("message") or "")
    assert payload["latest_run"]["order_items"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_explains_zero_executable_orders -v
```

Expected:

- FAIL because the current backend emits empty `items` and generic reconcile text instead of explicit skip messages

- [ ] **Step 3: Write the minimal implementation**

```python
# src/api/routes_dashboard.py
def _build_empty_execution_messages(decision_items: list[dict], target_items: list[dict]) -> dict[str, str]:
    if target_items:
        return {}

    buy_decisions = [row for row in decision_items if row.get("action") == "BUY"]
    sell_decisions = [row for row in decision_items if row.get("action") == "SELL"]

    if buy_decisions:
        return {
            "target": "资金不足或最小交易单位限制，未生成可执行订单",
            "execute": "无可执行订单，已跳过模拟执行",
            "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
        }
    if sell_decisions:
        return {
            "target": "当前无可卖持仓，未生成可执行订单",
            "execute": "无可执行订单，已跳过模拟执行",
            "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
        }
    return {
        "target": "本轮无买卖信号，未生成目标仓位",
        "execute": "无可执行订单，已跳过模拟执行",
        "reconcile": "未发生模拟成交，账户净值未变化。模拟盈亏: +¥0",
    }
```

```python
# src/api/routes_dashboard.py
def _build_run_timeline(
    run_context_id: str | None,
    watchlist: list[str],
    capital_base: int,
    decision_mode: str,
    decision_items: list[dict],
    target_items: list[dict],
    order_items: list[dict],
    decision_only: bool,
    daily_pnl: float,
) -> dict:
    now = _now_cst().isoformat()
    empty_messages = _build_empty_execution_messages(decision_items, target_items)

    target_done_step = {
        "stage": "target",
        "status": "done",
        "timestamp": now,
        "items": target_items,
    } if target_items else {
        "stage": "target",
        "status": "done",
        "timestamp": now,
        "message": empty_messages["target"],
    }

    steps = [
        {
            "stage": "decision",
            "status": "running",
            "timestamp": now,
            "message": f"输入标的: {', '.join(watchlist)} | 资金: ¥{capital_base:,} | 模式: {decision_mode}",
        },
        {
            "stage": "decision",
            "status": "done",
            "timestamp": now,
            "items": decision_items,
        },
        {
            "stage": "target",
            "status": "running",
            "timestamp": now,
            "message": "计算中...",
        },
        target_done_step,
    ]

    if decision_only:
        steps.append(
            {
                "stage": "reconcile",
                "status": "done",
                "timestamp": now,
                "message": "仅决策模式，跳过执行",
            }
        )
    elif order_items:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "running",
                    "timestamp": now,
                    "message": "发送订单中...",
                },
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": now,
                    "items": order_items,
                },
                {
                    "stage": "reconcile",
                    "status": "running",
                    "timestamp": now,
                    "message": "核对执行结果...",
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": now,
                    "message": f"所有订单已确认，持仓已更新。模拟盈亏: {_format_pnl_label(daily_pnl)}",
                },
            ]
        )
    else:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": now,
                    "message": empty_messages["execute"],
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": now,
                    "message": empty_messages["reconcile"],
                },
            ]
        )

    return {
        "run_context_id": run_context_id,
        "started_at": now,
        "finished_at": now,
        "status": "completed",
        "steps": steps,
        "order_items": order_items,
    }
```

```markdown
# docs/sop.md
- 在“点了保存或运行，不确定有没有真的成功”下面补一条：
  - 如果 `目标仓位` 显示“资金不足或最小交易单位限制，未生成可执行订单”，说明系统有建议，但按当前资金和最小交易单位无法成交。
- 在“快速回测 / 模拟交易 SOP”里补一句：
  - 美股默认按 1 股为最小单位，A 股默认按 100 股一手计算。
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py::test_run_endpoint_explains_zero_executable_orders -v
```

Then run the broader regression slice:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_rules.py tests/test_strategy_config.py tests/test_target_planner.py tests/test_dashboard_api.py tests/test_backtest_api.py -q
```

Expected:

- The new dashboard API regression passes
- No previously passing lot-size or dashboard tests regress

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py tests/test_dashboard_api.py docs/sop.md
git commit -m "feat: explain empty executable orders"
```

## Self-Review

- Spec coverage:
  - Explicit page feedback when no target/order is generated: covered in Task 3.
  - Split US and A-share lot sizes: covered in Tasks 1 and 2.
  - Avoid leaving backtest on the old shared lot size: covered in Task 2.
- Placeholder scan:
  - No `TODO`, `TBD`, or “similar to Task N” references remain.
- Type consistency:
  - `strategy_lot_size_a` / `strategy_lot_size_us`, `lot_size_a` / `lot_size_us`, and `resolve_lot_size(...)` names are used consistently across config, planner, routes, and tests.

