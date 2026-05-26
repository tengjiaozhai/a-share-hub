# 量化策略、回测与长期模拟盘改造 实施计划

> **给代理执行者：** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施本计划。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 把当前“dashboard 演示链路”改造成一条可解释、可回测、可长期 shadow 评估的单路径研究与模拟交易系统。

**架构：** 采用“确定性量化策略基线 + LLM 仅作候选增强/解释 + 确定性目标仓位/风控/OMS + PostgreSQL 权威落库”的单路径架构。回测、shadow、dashboard 三条路径共用同一套策略函数、目标仓位逻辑和账户状态回写，禁止再保留“固定数量 / 固定盈亏 / print 占位”的双轨逻辑。

**技术栈：** Python 3.11、FastAPI、PostgreSQL、AkShare、pandas、pytest

---

## 改造清单

- 修复 `src.main` 当前已经损坏的 CLI 决策入口，使 `decide`、`shadow-execute`、`reconcile` 成为真实命令，而不是 print 占位。
- 把当前策略从“对 watchlist 逐只调用 LLM + 固定仓位/固定数量”收敛为“确定性量化策略基线 + LLM overlay”。
- 新增权威的策略配置对象，统一策略参数、仓位上限、候选数、风控阈值，禁止 dashboard 和 CLI 各自硬编码。
- 新增 `backtest` 子系统，先做日频基线回测，再为后续 `15m`/盘中低频扩展打基础。
- 把 paper/shadow 交易从“固定价格 `100.0` + 固定数量 `200/300` + 固定盈亏 `_PAPER_DAILY_PNL`”改为“真实账户现金/持仓/市值驱动”。
- 新增 `AccountSnapshot`、`PositionSnapshot`、`EvaluationRun` 等长期评估必需实体。
- 新增长期评估命令，支持 `1m`、`3m`、`1y` 三个窗口，输出统一指标与报告。
- 更新 dashboard、README、SOP 和 runbook，使页面展示与真实仓库行为一致。

## 增量计划：实时行情 Tab 与轮询

### 目标

- 新增 `/api/v1/market/quote?symbol=xxx`，由 `AkshareProvider.get_realtime_quote()` 提供数据。
- 仪表盘新增“实时行情”Tab，展示最新价、开高低、涨跌幅、成交量。
- 前端按观察列表轮询行情接口，和现有“运行链路”并行工作，不互相阻塞。

### 实施任务

- [ ] **任务 A：补齐权威行情接口（后端）**
  - 文件：
    - `src/api/routes_market.py`（新增）
    - `src/main.py`（注册 router）
  - 行为：
    - GET `/api/v1/market/quote?symbol=600519.SH`
    - 调用 `AkshareProvider.get_realtime_quote(symbol)`
    - 返回标准 `MarketSnapshot` JSON
    - provider 不可用时返回 `503`，无数据返回 `404`

- [ ] **任务 B：修正 AkShare 实时行情字段映射（数据层）**
  - 文件：
    - `src/data/providers/akshare_provider.py`
  - 行为：
    - 把 AkShare 的“最新价/今开/最高/最低/成交量/成交额/买一/卖一”等字段映射到 `MarketSnapshot` 的 `open/high/low/close/volume/amount/bid/ask`。
    - 去掉不在 `MarketSnapshot` schema 内的字段，避免运行时校验失败。

- [ ] **任务 C：新增仪表盘行情展示 Tab 与轮询（前端）**
  - 文件：
    - `src/api/dashboard.html`
  - 行为：
    - 新增 tab 切换项“实时行情”
    - 新增行情表格区（时间、股票、最新价、今开、最高、最低、涨跌幅、成交量）
    - 轮询 `/api/v1/market/quote?symbol=xxx`（按观察列表逐只拉取）
    - 请求失败时不打断主页面，行情区展示“暂无行情数据”或保留已有数据

### 验收标准

- [ ] **接口验收**
  - `GET /api/v1/market/quote?symbol=600519.SH` 返回 `200`，并包含：
    - `symbol`
    - `timestamp`
    - `open`
    - `high`
    - `low`
    - `close`
    - `volume`
    - `amount`

- [ ] **页面验收**
  - `http://127.0.0.1:8010/dashboard` 底部区域存在“实时行情”Tab，并可与其它 Tab 正常切换。
  - 行情表格每轮轮询会刷新，至少包含观察列表中的 1 只股票数据。
  - 行情接口异常时，决策/执行时间线、运行按钮、风控区保持可用。

- [ ] **回归验收**
  - 现有接口 `/api/v1/dashboard/workbench`、`/api/v1/dashboard/run` 返回结构不变。
  - 新增测试通过，且不依赖 SQLite。

## 目标量化策略定义

本次改造不建议继续把“LLM 本身”当作唯一策略，而是收敛成两层：

1. **确定性量化策略基线**
   - 标的范围：Phase 1 先支持用户 `watchlist`；Phase 4 再扩展到 AkShare 股票池。
   - 频率：Phase 1 先做日频；Phase 4 再扩展到 `15m` 盘中低频。
   - 特征：`ma20_gap`、`ma60_gap`、`momentum_20`、`momentum_60`、`rsi_14`、`volatility_20`、`volume_ratio_20`。
   - 评分：`0.30 * momentum_20 + 0.25 * momentum_60 + 0.20 * ma20_gap + 0.15 * ma60_gap + 0.10 * volume_ratio_20 - 0.10 * volatility_20`。
   - 信号：
     - `BUY`：评分 `>= 0.55`，且 `45 <= rsi_14 <= 72`
     - `SELL`：评分 `<= -0.20`，或 `rsi_14 >= 80`，或 `ma20_gap <= -0.05`
     - `HOLD`：其余情况

2. **LLM Overlay**
   - 只作用于确定性策略筛出的 Top-N 候选，不允许绕过基线策略直接下单。
   - 只负责：
     - 解释原因
     - 调整置信度
     - 在 `BUY/HOLD/SELL` 同方向上做轻微仓位缩放
   - 不负责：
     - 生成订单
     - 控制 broker 状态
     - 处理撤单/对账/风控

3. **长期评估口径**
   - `1m`：验证链路是否稳定，不以收益率为主。
   - `3m`：验证策略是否在连续交易日内保持一致、日志是否完整、回测与 shadow 偏差是否可解释。
   - `1y`：验证策略在不同市场环境下的收益、回撤、换手、稳定性，不把单一年份收益率作为唯一成败标准。

## 文件结构

- 新建：`src/strategy/strategy_config.py`
  - 策略参数的唯一配置入口。
- 新建：`src/strategy/signal_engine.py`
  - 量化特征转信号、评分和目标仓位权重。
- 新建：`src/backtest/__init__.py`
- 新建：`src/backtest/engine.py`
  - 日频回测主循环，生成净值曲线、交易记录、调仓记录。
- 新建：`src/backtest/metrics.py`
  - 收益率、回撤、换手、胜率、Sharpe、信息比率等指标。
- 新建：`src/backtest/reporting.py`
  - 把回测和长期 shadow 结果输出成 JSON / Markdown。
- 新建：`src/execution/paper_portfolio.py`
  - 模拟账户现金、持仓、均价、市值、已实现/未实现盈亏。
- 新建：`src/evaluation/long_run.py`
  - `1m/3m/1y` 评估窗口、检查点恢复和报告汇总。
- 修改：`src/main.py`
  - 修复 CLI，并新增 `backtest`、`evaluate-shadow` 命令。
- 修改：`src/core/config.py`
  - 增加策略参数、评估窗口、报告输出目录等配置。
- 修改：`src/indicators/technical_indicators.py`
  - 扩展现有指标输出。
- 修改：`src/strategy/candidate_filter.py`
  - 接入评分和 Top-N 筛选。
- 修改：`src/decision/input_builder.py`
  - 把确定性特征、基线信号、候选评分写入决策快照。
- 修改：`src/api/routes_dashboard.py`
  - 移除固定数量/固定盈亏占位逻辑，改为真实 paper 账户回写。
- 修改：`src/execution/paper_broker.py`
  - 支持基于报价成交和事件回放，而不是随机填单为主。
- 修改：`src/execution/reconciliation.py`
  - 接入账户快照与持仓对账。
- 修改：`src/storage/models.py`
  - 新增 `AccountSnapshotRow`、`PositionSnapshotRow`、`EvaluationRunRow`。
- 修改：`src/storage/runtime_store.py`
  - 新增账户快照、评估运行、回测结果的读写接口。
- 修改：`scripts/run_shadow_cycle.sh`
  - 让其执行真实命令，不再依赖坏掉的 CLI 路径。
- 修改：`docs/sop.md`、`README.md`、`docs/runbooks/dashboard_user_guide.md`
  - 更新长期评估和回测入口。
- 新建测试：
  - `tests/test_strategy_signal_engine.py`
  - `tests/test_backtest_engine.py`
  - `tests/test_backtest_metrics.py`
  - `tests/test_paper_portfolio.py`
  - `tests/test_long_run_evaluation.py`

### 任务 1：修复权威路径并冻结策略配置

**文件：**
- 新建：`src/strategy/strategy_config.py`
- 修改：`src/main.py`
- 修改：`src/core/config.py`
- 测试：`tests/test_cli.py`
- 测试：`tests/test_config_env.py`

- [ ] **步骤 1：先写失败测试**

```python
from src.main import run_decide_command


def test_run_decide_command_uses_mock_settings_without_constructor_kwargs(runtime_store, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    summary = run_decide_command(symbols=["600519.SH"], mock_llm=True, store=runtime_store)

    assert summary["status"] == "ok"
    assert len(summary["decision_run_ids"]) == 1


def test_settings_exposes_strategy_defaults(monkeypatch):
    monkeypatch.setenv("STRATEGY_TOP_N", "10")
    monkeypatch.setenv("STRATEGY_MAX_POSITION_RATIO", "0.2")

    settings = Settings()

    assert settings.strategy_top_n == 10
    assert settings.strategy_max_position_ratio == 0.2
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_cli.py::test_run_decide_command_uses_mock_settings_without_constructor_kwargs tests/test_config_env.py::test_settings_exposes_strategy_defaults -v`

预期：FAIL，`run_decide_command()` 触发 `LLMClient.__init__() got an unexpected keyword argument 'provider'`，且 `Settings` 中不存在策略配置字段。

- [ ] **步骤 3：编写最小实现**

```python
# src/strategy/strategy_config.py
from dataclasses import dataclass

from src.core.config import Settings


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int
    max_position_ratio: float
    buy_score_threshold: float
    sell_score_threshold: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "StrategyConfig":
        return cls(
            top_n=settings.strategy_top_n,
            max_position_ratio=settings.strategy_max_position_ratio,
            buy_score_threshold=settings.strategy_buy_score_threshold,
            sell_score_threshold=settings.strategy_sell_score_threshold,
        )
```

```python
# src/main.py
from src.core.config import Settings


def _build_cli_llm_client(mock_llm: bool) -> LLMClient:
    if not mock_llm:
        return LLMClient()
    settings = Settings(llm_provider="mock", llm_api_key="")
    return LLMClient(settings=settings)


def run_decide_command(symbols: list[str], mock_llm: bool, store=None) -> dict:
    runtime_store = store or get_runtime_store()
    if runtime_store.get_kill_switch():
        return {"status": "blocked", "reason": "kill switch enabled", "decision_run_ids": [], "target_position_ids": []}

    client = _build_cli_llm_client(mock_llm)
```

```python
# src/core/config.py
class Settings(BaseSettings):
    ...
    strategy_top_n: int = 10
    strategy_max_position_ratio: float = 0.2
    strategy_buy_score_threshold: float = 0.55
    strategy_sell_score_threshold: float = -0.20
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_cli.py tests/test_config_env.py -v`

预期：PASS，`decide` 不再因为 `provider` 参数崩溃，策略配置可以通过 `Settings` 读取。

- [ ] **步骤 5：提交**

```bash
git add src/main.py src/core/config.py src/strategy/strategy_config.py tests/test_cli.py tests/test_config_env.py
git commit -m "fix: repair decide cli and add strategy config"
```

### 任务 2：实现权威量化策略基线

**文件：**
- 新建：`src/strategy/signal_engine.py`
- 修改：`src/indicators/technical_indicators.py`
- 修改：`src/strategy/candidate_filter.py`
- 修改：`src/decision/input_builder.py`
- 修改：`src/main.py`
- 修改：`src/api/routes_dashboard.py`
- 测试：`tests/test_indicators.py`
- 测试：`tests/test_candidate_filter.py`
- 测试：`tests/test_strategy_signal_engine.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_compute_feature_row_returns_extended_feature_set():
    close_prices = [100 + i for i in range(80)]

    row = compute_feature_row(close_prices)

    assert set(row) >= {
        "ma20_gap",
        "ma60_gap",
        "momentum_20",
        "momentum_60",
        "rsi_14",
        "volatility_20",
    }


def test_build_signal_returns_buy_for_high_score():
    config = StrategyConfig(top_n=10, max_position_ratio=0.2, buy_score_threshold=0.55, sell_score_threshold=-0.2)
    features = {
        "ma20_gap": 0.08,
        "ma60_gap": 0.12,
        "momentum_20": 0.15,
        "momentum_60": 0.22,
        "rsi_14": 58,
        "volatility_20": 0.03,
        "volume_ratio_20": 1.40,
    }

    signal = build_signal("600519.SH", features, config)

    assert signal["action"] == "BUY"
    assert signal["technical_score"] >= 0.55
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_indicators.py tests/test_candidate_filter.py tests/test_strategy_signal_engine.py -v`

预期：FAIL，当前指标函数缺少扩展特征，且仓库中不存在 `signal_engine.py`。

- [ ] **步骤 3：编写最小实现**

```python
# src/indicators/technical_indicators.py
def compute_feature_row(close_prices: list[float]) -> dict[str, float]:
    if len(close_prices) < 60:
        return {
            "ma20_gap": 0.0,
            "ma60_gap": 0.0,
            "momentum_20": 0.0,
            "momentum_60": 0.0,
            "rsi_14": 50.0,
            "volatility_20": 0.0,
            "volume_ratio_20": 1.0,
        }
```

```python
# src/strategy/signal_engine.py
from src.strategy.strategy_config import StrategyConfig


def compute_technical_score(features: dict[str, float]) -> float:
    return (
        0.30 * features["momentum_20"]
        + 0.25 * features["momentum_60"]
        + 0.20 * features["ma20_gap"]
        + 0.15 * features["ma60_gap"]
        + 0.10 * features["volume_ratio_20"]
        - 0.10 * features["volatility_20"]
    )


def build_signal(symbol: str, features: dict[str, float], config: StrategyConfig) -> dict[str, float | str]:
    score = compute_technical_score(features)
    rsi = features["rsi_14"]
    if score >= config.buy_score_threshold and 45 <= rsi <= 72:
        action = "BUY"
    elif score <= config.sell_score_threshold or rsi >= 80 or features["ma20_gap"] <= -0.05:
        action = "SELL"
    else:
        action = "HOLD"
    return {"symbol": symbol, "action": action, "technical_score": score}
```

```python
# src/strategy/candidate_filter.py
def rank_candidates(rows: list[dict], top_n: int) -> list[dict]:
    return sorted(rows, key=lambda row: row["technical_score"], reverse=True)[:top_n]
```

```python
# src/decision/input_builder.py
def build_decision_input_snapshot(symbol: str, features: dict, market_context: dict, technical_features: dict | None = None, base_signal: dict | None = None) -> dict:
    return {
        "symbol": symbol,
        "features": features,
        "market_context": market_context,
        "technical_features": technical_features or {},
        "base_signal": base_signal or {},
    }
```

```python
# src/api/routes_dashboard.py
strategy_config = StrategyConfig.from_settings(settings)
technical_features = compute_feature_row(close_prices)
base_signal = build_signal(symbol, technical_features, strategy_config)
snapshot = build_decision_input_snapshot(
    symbol=symbol,
    features=payload,
    market_context={"mode": "shadow", "run_context_id": run_context_id},
    technical_features=technical_features,
    base_signal=base_signal,
)
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_indicators.py tests/test_candidate_filter.py tests/test_strategy_signal_engine.py tests/test_dashboard_api.py -v`

预期：PASS，量化策略基线可以独立地产出确定性信号，且 dashboard / CLI 决策快照都能记录 `technical_features` 和 `base_signal`。

- [ ] **步骤 5：提交**

```bash
git add src/indicators/technical_indicators.py src/strategy/candidate_filter.py src/strategy/signal_engine.py src/decision/input_builder.py src/main.py src/api/routes_dashboard.py tests/test_indicators.py tests/test_candidate_filter.py tests/test_strategy_signal_engine.py tests/test_dashboard_api.py
git commit -m "feat: add deterministic quant strategy baseline"
```

### 任务 3：新增回测引擎并接入 CLI

**文件：**
- 新建：`src/backtest/__init__.py`
- 新建：`src/backtest/engine.py`
- 新建：`src/backtest/metrics.py`
- 新建：`src/backtest/reporting.py`
- 修改：`src/main.py`
- 测试：`tests/test_backtest_engine.py`
- 测试：`tests/test_backtest_metrics.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_run_daily_backtest_produces_equity_curve_and_trades():
    bars = [
        {"date": "2025-01-02", "close": 100.0},
        {"date": "2025-01-03", "close": 102.0},
        {"date": "2025-01-06", "close": 104.0},
    ]

    result = run_daily_backtest(
        symbol="600519.SH",
        bars=bars,
        initial_cash=1_000_000.0,
        signals=[
            {"date": "2025-01-02", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2025-01-06", "action": "SELL", "target_position_ratio": 0.0},
        ],
    )

    assert len(result["equity_curve"]) == 3
    assert len(result["trades"]) == 2
    assert result["final_nav"] > 0


def test_calculate_metrics_returns_drawdown_and_turnover():
    metrics = calculate_metrics(
        equity_curve=[1.0, 1.02, 0.99, 1.05],
        trades=[{"side": "BUY", "notional": 100000}, {"side": "SELL", "notional": 100000}],
    )

    assert set(metrics) >= {"total_return", "max_drawdown", "turnover", "win_rate"}
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_engine.py tests/test_backtest_metrics.py -v`

预期：FAIL，仓库中不存在 `src/backtest/` 子系统和 `backtest` CLI。

- [ ] **步骤 3：编写最小实现**

```python
# src/backtest/engine.py
def run_daily_backtest(symbol: str, bars: list[dict], initial_cash: float, signals: list[dict]) -> dict:
    cash = initial_cash
    position = 0
    equity_curve = []
    trades = []
    signal_by_date = {row["date"]: row for row in signals}

    for bar in bars:
        signal = signal_by_date.get(bar["date"])
        if signal and signal["action"] == "BUY":
            target_value = initial_cash * signal["target_position_ratio"]
            quantity = int(target_value / bar["close"])
            cash -= quantity * bar["close"]
            position += quantity
            trades.append({"date": bar["date"], "side": "BUY", "quantity": quantity, "notional": quantity * bar["close"]})
        elif signal and signal["action"] == "SELL" and position > 0:
            cash += position * bar["close"]
            trades.append({"date": bar["date"], "side": "SELL", "quantity": position, "notional": position * bar["close"]})
            position = 0

        equity_curve.append(cash + position * bar["close"])

    return {"equity_curve": equity_curve, "trades": trades, "final_nav": equity_curve[-1]}
```

```python
# src/backtest/metrics.py
def calculate_metrics(equity_curve: list[float], trades: list[dict]) -> dict:
    start = equity_curve[0]
    end = equity_curve[-1]
    peak = max(equity_curve)
    drawdown = min((value - peak) / peak for value in equity_curve)
    turnover = sum(row["notional"] for row in trades) / start
    return {
        "total_return": (end - start) / start,
        "max_drawdown": drawdown,
        "turnover": turnover,
        "win_rate": 0.0,
    }
```

```python
# src/main.py
p_backtest = subparsers.add_parser("backtest", help="运行日频回测")
p_backtest.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
p_backtest.add_argument("--start", required=True, help="开始日期")
p_backtest.add_argument("--end", required=True, help="结束日期")
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_engine.py tests/test_backtest_metrics.py tests/test_cli.py -v`

预期：PASS，`backtest` 子系统可独立运行并输出权威指标。

- [ ] **步骤 5：提交**

```bash
git add src/backtest src/main.py tests/test_backtest_engine.py tests/test_backtest_metrics.py tests/test_cli.py
git commit -m "feat: add daily backtest engine and cli"
```

### 任务 4：把 shadow/paper 交易改成真实账户驱动

**文件：**
- 新建：`src/execution/paper_portfolio.py`
- 修改：`src/execution/paper_broker.py`
- 修改：`src/execution/reconciliation.py`
- 修改：`src/storage/models.py`
- 修改：`src/storage/runtime_store.py`
- 修改：`src/api/routes_dashboard.py`
- 测试：`tests/test_shadow_execution.py`
- 测试：`tests/test_paper_portfolio.py`
- 测试：`tests/test_dashboard_api.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_apply_fill_updates_cash_position_and_average_cost():
    state = {"cash": 1_000_000.0, "positions": {}}

    new_state = apply_fill(
        state=state,
        symbol="600519.SH",
        side="BUY",
        quantity=100,
        price=1200.0,
    )

    assert new_state["cash"] == 880000.0
    assert new_state["positions"]["600519.SH"]["quantity"] == 100
    assert new_state["positions"]["600519.SH"]["avg_cost"] == 1200.0


def test_dashboard_run_uses_mark_to_market_pnl_instead_of_fixed_placeholder(test_app, monkeypatch):
    response = client.post("/api/v1/dashboard/run", json={"watchlist": ["600519.SH"], "decision_mode": "mock", "execution_mode": "full"})
    payload = response.json()

    reconcile_step = payload["latest_run"]["steps"][-1]

    assert "模拟盈亏:" in reconcile_step["message"]
    assert "+¥1,250" not in reconcile_step["message"]
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_shadow_execution.py tests/test_paper_portfolio.py tests/test_dashboard_api.py -v`

预期：FAIL，当前账户状态不存在，dashboard 仍然依赖固定价格、固定数量和固定 `_PAPER_DAILY_PNL`。

- [ ] **步骤 3：编写最小实现**

```python
# src/execution/paper_portfolio.py
def apply_fill(state: dict, symbol: str, side: str, quantity: int, price: float) -> dict:
    cash = state["cash"]
    positions = dict(state["positions"])
    position = dict(positions.get(symbol, {"quantity": 0, "avg_cost": 0.0}))

    if side == "BUY":
        cash -= quantity * price
        total_qty = position["quantity"] + quantity
        total_cost = position["quantity"] * position["avg_cost"] + quantity * price
        position = {"quantity": total_qty, "avg_cost": total_cost / total_qty}
    else:
        cash += quantity * price
        position = {"quantity": max(position["quantity"] - quantity, 0), "avg_cost": position["avg_cost"]}

    positions[symbol] = position
    return {"cash": cash, "positions": positions}
```

```python
# src/storage/models.py
class AccountSnapshotRow(Base):
    __tablename__ = "account_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/api/routes_dashboard.py
quote_price = _get_shadow_mark_price(symbol)
execution_order_id = store.insert_execution_order(
    target_position_id=target_position_id,
    symbol=symbol,
    action=parsed_action,
    quantity=target_quantity,
    limit_price=quote_price,
)
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_shadow_execution.py tests/test_paper_portfolio.py tests/test_dashboard_api.py -v`

预期：PASS，paper 账户的现金、持仓和盈亏由成交与市值决定，dashboard 不再显示固定占位盈亏。

- [ ] **步骤 5：提交**

```bash
git add src/execution/paper_portfolio.py src/execution/paper_broker.py src/execution/reconciliation.py src/storage/models.py src/storage/runtime_store.py src/api/routes_dashboard.py tests/test_shadow_execution.py tests/test_paper_portfolio.py tests/test_dashboard_api.py
git commit -m "feat: replace placeholder paper pnl with account-driven shadow execution"
```

### 任务 5：让长期评估成为一等能力

**文件：**
- 新建：`src/evaluation/long_run.py`
- 修改：`src/main.py`
- 修改：`scripts/run_shadow_cycle.sh`
- 新建：`docs/runbooks/long-horizon-evaluation.md`
- 修改：`README.md`
- 修改：`docs/sop.md`
- 测试：`tests/test_long_run_evaluation.py`
- 测试：`tests/test_e2e_shadow_cycle.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_run_long_horizon_evaluation_supports_1m_3m_1y_windows(runtime_store):
    result = run_long_horizon_evaluation(
        store=runtime_store,
        window="3m",
        mode="shadow",
    )

    assert result["window"] == "3m"
    assert set(result["metrics"]) >= {
        "total_return",
        "max_drawdown",
        "turnover",
        "decision_count",
        "fill_rate",
        "unreconciled_order_count",
    }


def test_shadow_cycle_script_calls_real_cli_commands():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "src.main decide" in script
    assert "src.main shadow-execute" in script
    assert "src.main reconcile" in script
    assert "src.main evaluate-shadow --window 1m" in script
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_long_run_evaluation.py tests/test_e2e_shadow_cycle.py -v`

预期：FAIL，仓库中不存在 `run_long_horizon_evaluation()`，且 shadow 脚本没有长期评估步骤。

- [ ] **步骤 3：编写最小实现**

```python
# src/evaluation/long_run.py
def run_long_horizon_evaluation(store, window: str, mode: str) -> dict:
    metrics = {
        "total_return": 0.0,
        "max_drawdown": 0.0,
        "turnover": 0.0,
        "decision_count": len(store.list_decision_runs()),
        "fill_rate": 1.0,
        "unreconciled_order_count": store.get_reconciliation_status()["open_orders"],
    }
    return {"window": window, "mode": mode, "metrics": metrics}
```

```python
# src/main.py
p_eval = subparsers.add_parser("evaluate-shadow", help="运行长期 shadow 评估")
p_eval.add_argument("--window", choices=["1m", "3m", "1y"], required=True, help="评估窗口")
```

```bash
# scripts/run_shadow_cycle.sh
"${PYTHON}" -m src.main decide --symbols 600519.SH --mock-llm
"${PYTHON}" -m src.main shadow-execute --symbols 600519.SH --mock-broker
"${PYTHON}" -m src.main reconcile --symbols 600519.SH
"${PYTHON}" -m src.main evaluate-shadow --window 1m
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_long_run_evaluation.py tests/test_e2e_shadow_cycle.py -v`

预期：PASS，shadow 运行结束后可以直接生成长期评估指标。

- [ ] **步骤 5：提交**

```bash
git add src/evaluation/long_run.py src/main.py scripts/run_shadow_cycle.sh docs/runbooks/long-horizon-evaluation.md README.md docs/sop.md tests/test_long_run_evaluation.py tests/test_e2e_shadow_cycle.py
git commit -m "feat: add long-horizon shadow evaluation"
```

## 分阶段验收标准

### Phase 1：策略基线与 CLI 修复

- 验收命令：
  - `TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_cli.py tests/test_config_env.py tests/test_indicators.py tests/test_candidate_filter.py tests/test_strategy_signal_engine.py -v`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main decide --symbols 600519.SH --mock-llm`
- 通过标准：
  - `decide` 命令不再抛出 `provider` 构造异常。
  - 策略参数全部来自 `Settings`/`StrategyConfig`，仓库中不再出现新的策略硬编码。
  - 给定同一组价格序列，信号输出稳定、可重复、可测试。
  - 决策快照中能看到 `technical_features` 和 `base_signal`，不再只有原始 LLM 文本。

### Phase 2：回测基线

- 验收命令：
  - `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_engine.py tests/test_backtest_metrics.py -v`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main backtest --symbols 600519.SH --start 2025-01-01 --end 2025-03-31`
- 通过标准：
  - 回测命令能输出净值曲线、交易记录和指标。
  - 回测结果至少包含 `total_return`、`max_drawdown`、`turnover`、`win_rate`。
  - 回测使用的策略函数与实盘/shadow 共用同一实现，而不是复制一份逻辑。

### Phase 3：真实 shadow/paper 交易

- 验收命令：
  - `TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_shadow_execution.py tests/test_paper_portfolio.py tests/test_dashboard_api.py tests/test_reconciliation.py -v`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main shadow-execute --symbols 600519.SH --mock-broker`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main reconcile --symbols 600519.SH`
- 通过标准：
  - `shadow-execute` 和 `reconcile` 不再只是 print。
  - 每个执行订单都能关联到 `broker_event`、`account_snapshot`、`position_snapshot`。
  - dashboard 中的盈亏、现金、持仓来自真实 paper 账户计算，而不是固定占位值。
  - 日终 `open_orders == 0`，不存在未对账订单。

### Phase 4：长期评估

- 验收命令：
  - `TEST_DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub_test /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_long_run_evaluation.py tests/test_e2e_shadow_cycle.py -v`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1m`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 3m`
  - `/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1y`
- 通过标准：
  - `1m` 评估能输出链路可用性指标：`decision_count`、`fill_rate`、`unreconciled_order_count`。
  - `3m` 评估能输出收益和风控指标：`total_return`、`max_drawdown`、`turnover`。
  - `1y` 评估可以完整跑完并产出报告，不要求收益一定为正，但必须有完整指标和日志。
  - 支持从上一次检查点恢复，不要求一次性连续跑完整个一年窗口。

### Phase 5：长期 shadow 准入门槛

- 验收命令：
  - 连续运行 `20` 个交易日 shadow 周期
  - 每日运行一次 `evaluate-shadow --window 1m`
  - 每周运行一次 `evaluate-shadow --window 3m`
- 通过标准：
  - 连续 `20` 个交易日内，不允许人工改数据库修单。
  - 每个 `decision_run` 都能追溯到目标仓位、执行订单、broker 回报和对账结果。
  - 影子交易日志、回测结果和长期评估报告三者口径一致。
  - 达到本阶段后，系统才可被标记为 `shadow-ready`；未完成前不得宣传为“可长期模拟评估”。

## 自检结论

- **Spec coverage：** 已覆盖三类目标：量化策略、回测、长期模拟盘评估。
- **Placeholder scan：** 计划中未保留 `TODO/TBD/implement later` 类占位语句。
- **Type consistency：** 计划统一使用 `StrategyConfig`、`run_daily_backtest()`、`run_long_horizon_evaluation()`、`AccountSnapshotRow`、`PositionSnapshotRow` 这些名称，不再与现有 CLI 命名混用。

**计划已完成，并保存到 `docs/superpowers/plans/2026-05-26-quant-strategy-backtest-shadow-plan.md`。有两种执行方式：**

**1. Subagent-Driven（推荐）** - 我按任务派发新的子代理执行，在任务之间做评审，迭代更快

**2. Inline Execution** - 我在当前会话中使用 `executing-plans` 执行这些任务，按检查点分批推进

**请选择哪一种方式？**
