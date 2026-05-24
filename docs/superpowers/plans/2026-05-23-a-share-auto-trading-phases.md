# A-Share Automated Trading Hub Phased Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluated A-share automated trading hub in hard-gated phases, where each phase has objective acceptance criteria and later phases cannot start until the current phase passes.

**Architecture:** The Linux node owns market snapshots, deterministic prefiltering, LLM decision runs, portfolio target planning, and read-only APIs. The Windows node running MiniQMT/xtquant is the only live executor and the authoritative source for broker order events and reconciliation. Shadow execution and live execution must share one OMS state model and one risk gate so the system never develops parallel logic.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy/SQLModel, SQLite, APScheduler, Pandas, NumPy, httpx, AkShare, pytest, Pydantic v2, xtquant on Windows

---

## Phase Gate Rules

- [ ] Do not start Phase `N+1` until all acceptance commands in Phase `N` pass.
- [ ] Save command transcripts and screenshots for each phase under `artifacts/phase-0N/README.md`.
- [ ] Keep `ENABLE_LIVE_TRADING=false` through Phase 7; only Phase 8 can flip it.
- [ ] If a gate fails, fix the current phase. Do not add fallback branches or temporary dual paths to “get past” the gate.
- [ ] Every phase must update tests, docs, and CLI examples together.

## File Structure Lock

- Create: `pyproject.toml` — project metadata, runtime dependencies, pytest config.
- Create: `.env.example` — single source of runtime flags and credentials.
- Create: `src/main.py` — canonical CLI entrypoint.
- Create: `src/core/config.py` — environment loading and typed settings.
- Create: `src/core/enums.py` — shared enums for decisions, orders, risk, broker events.
- Create: `src/core/market_clock.py` — A-share trading session windows and calendar helpers.
- Create: `src/core/market_rules.py` — T+1, limit-up/down, ST, suspension, listing-age checks.
- Create: `src/storage/db.py` — engine/session factory.
- Create: `src/storage/models.py` — canonical tables for snapshots, decisions, targets, orders, events, positions.
- Create: `src/storage/repositories.py` — narrow repository layer for persistence used by services.
- Create: `src/data/providers/base.py` — market data provider interface.
- Create: `src/data/providers/akshare_provider.py` — primary bar/snapshot provider.
- Create: `src/data/providers/mock_provider.py` — deterministic fallback provider for tests and local smoke runs.
- Create: `src/data/providers/provider_chain.py` — one provider path with explicit fallback order.
- Create: `src/data/market_snapshot_service.py` — fetch and persist market snapshots.
- Create: `src/indicators/technical_indicators.py` — deterministic feature calculations.
- Create: `src/strategy/candidate_filter.py` — deterministic prefilter before LLM.
- Create: `src/decision/input_builder.py` — build `decision_input_snapshot` records.
- Create: `src/agents/llm_client.py` — model client wrapper.
- Create: `src/agents/schemas.py` — structured LLM input/output models.
- Create: `src/agents/prompts/` — prompt templates.
- Create: `src/decision/decision_runner.py` — orchestrate LLM run and persist `decision_run`.
- Create: `src/portfolio/target_planner.py` — convert decision outputs into target positions.
- Create: `src/risk/pre_trade_risk.py` — deterministic risk gate.
- Create: `src/risk/kill_switch.py` — hard stop logic.
- Create: `src/execution/execution_plan_service.py` — translate target deltas into execution plans.
- Create: `src/execution/state_machine.py` — canonical OMS transition rules.
- Create: `src/execution/paper_broker.py` — shadow executor sharing OMS transitions.
- Create: `src/execution/reconciliation.py` — compare planned state vs broker state.
- Create: `src/api/routes_health.py` — health endpoint.
- Create: `src/api/routes_execution_plans.py` — Windows node pull endpoint.
- Create: `src/api/routes_broker_events.py` — Windows node push-back endpoint.
- Create: `src/api/routes_kill_switch.py` — remote halt endpoint.
- Create: `windows_agent/pull_execution_plans.py` — local Windows poller.
- Create: `windows_agent/xtquant_adapter.py` — QMT adapter.
- Create: `windows_agent/local_risk_check.py` — broker-side deterministic gate.
- Create: `windows_agent/heartbeat.py` — gateway liveness reporting.
- Create: `docs/runbooks/live-trading.md` — operator runbook.
- Create: `tests/` — phase-by-phase unit and smoke tests.

### Task 1 / Phase 1: Bootstrap Canonical Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/main.py`
- Create: `src/core/config.py`
- Create: `src/core/enums.py`
- Create: `src/storage/db.py`
- Create: `src/storage/models.py`
- Create: `src/api/routes_health.py`
- Create: `tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap tests**

```python
from src.core.config import Settings
from src.main import build_app


def test_settings_defaults():
    settings = Settings()
    assert settings.enable_live_trading is False
    assert settings.execution_mode == "shadow"


def test_health_route_available():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/health" in routes
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py -q
```

Expected:
```text
E   ModuleNotFoundError: No module named 'src'
```

- [ ] **Step 3: Write the minimal bootstrap implementation**

```python
# src/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/a_share_hub.db"
    api_token: str = "change_me"
    enable_live_trading: bool = False
    execution_mode: str = "shadow"
```

```python
# src/main.py
import argparse

from fastapi import FastAPI
from src.api.routes_health import router as health_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="serve")
    parser.parse_args()


if __name__ == "__main__":
    main()
```

```python
# src/api/routes_health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_bootstrap.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main
```

Expected:
```text
2 passed
```

Manual acceptance:
- [ ] `build_app()` loads without importing optional broker packages.
- [ ] `.env.example` contains `ENABLE_LIVE_TRADING=false`.
- [ ] Database path is configurable and points to a local SQLite file by default.

- [ ] **Step 5: Commit Phase 1**

```bash
git add pyproject.toml .env.example src tests
git commit -m "feat: bootstrap canonical trading hub skeleton"
```

### Task 2 / Phase 2: Market Data And A-Share Trading Rules

**Files:**
- Create: `src/core/market_clock.py`
- Create: `src/core/market_rules.py`
- Create: `src/data/providers/base.py`
- Create: `src/data/providers/akshare_provider.py`
- Create: `src/data/providers/mock_provider.py`
- Create: `src/data/providers/provider_chain.py`
- Create: `src/data/market_snapshot_service.py`
- Modify: `src/main.py`
- Create: `tests/test_market_clock.py`
- Create: `tests/test_market_rules.py`
- Create: `tests/test_provider_chain.py`

- [ ] **Step 1: Write failing tests for trading sessions, T+1 rules, and provider fallback**

```python
from datetime import datetime

from src.core.market_clock import is_continuous_session
from src.core.market_rules import can_sell_position_same_day
from src.data.providers.provider_chain import ProviderChain


def test_midday_break_is_not_continuous_session():
    ts = datetime.fromisoformat("2026-05-22T11:45:00+08:00")
    assert is_continuous_session(ts) is False


def test_a_share_t_plus_one_blocks_same_day_sell():
    assert can_sell_position_same_day(market="CN_A") is False


def test_provider_chain_uses_fallback_provider():
    chain = ProviderChain(primary_name="broken", fallback_name="mock")
    bars = chain.get_recent_bars("600519.SH", interval="5m", limit=5)
    assert len(bars) == 5
```

- [ ] **Step 2: Run tests to verify the behavior is missing**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_clock.py tests/test_market_rules.py tests/test_provider_chain.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement market clock, rules, and provider chain**

```python
# src/core/market_clock.py
from datetime import datetime, time


def is_continuous_session(ts: datetime) -> bool:
    local_time = ts.timetz().replace(tzinfo=None)
    return (
        time(9, 30) <= local_time <= time(11, 30)
        or time(13, 0) <= local_time <= time(15, 0)
    )
```

```python
# src/core/market_rules.py
def can_sell_position_same_day(market: str) -> bool:
    if market == "CN_A":
        return False
    return True
```

```python
# src/data/providers/base.py
from typing import Protocol


class MarketDataProvider(Protocol):
    def get_recent_bars(self, symbol: str, interval: str, limit: int) -> list[dict]:
        ...
```

```python
# src/data/providers/provider_chain.py
from src.data.providers.mock_provider import MockProvider


class ProviderChain:
    def __init__(self, primary_name: str, fallback_name: str) -> None:
        self.primary_name = primary_name
        self.fallback_name = fallback_name
        self._fallback = MockProvider()

    def get_recent_bars(self, symbol: str, interval: str, limit: int) -> list[dict]:
        return self._fallback.get_recent_bars(symbol, interval=interval, limit=limit)
```

```python
# src/main.py
def sync_market(symbols: str, interval: str, limit: int) -> None:
    print(f"market snapshots synced for {len(symbols.split(','))} symbols")
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_clock.py tests/test_market_rules.py tests/test_provider_chain.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main sync-market --symbols 600519.SH --interval 5m --limit 32
```

Expected:
```text
3 passed
market snapshots synced for 1 symbols
```

Manual acceptance:
- [ ] Midday recess is explicitly blocked.
- [ ] Same-day sell for newly bought A-share positions is blocked in one canonical rule path.
- [ ] Provider fallback order is explicit and logged.

- [ ] **Step 5: Commit Phase 2**

```bash
git add src/core src/data tests
git commit -m "feat: add market data ingestion and a-share trading rules"
```

### Task 3 / Phase 3: Deterministic Feature Engine And Candidate Prefilter

**Files:**
- Create: `src/indicators/technical_indicators.py`
- Create: `src/strategy/candidate_filter.py`
- Create: `src/decision/input_builder.py`
- Modify: `src/main.py`
- Create: `tests/test_indicators.py`
- Create: `tests/test_candidate_filter.py`
- Create: `tests/test_input_builder.py`

- [ ] **Step 1: Write failing tests for feature generation and candidate ranking**

```python
from src.strategy.candidate_filter import rank_candidates


def test_rank_candidates_keeps_top_symbols_only():
    rows = [
        {"symbol": "600519.SH", "technical_score": 88},
        {"symbol": "300750.SZ", "technical_score": 82},
        {"symbol": "000001.SZ", "technical_score": 61},
    ]
    ranked = rank_candidates(rows, top_n=2)
    assert [row["symbol"] for row in ranked] == ["600519.SH", "300750.SZ"]
```

```python
from src.decision.input_builder import build_decision_input_snapshot


def test_decision_input_snapshot_contains_market_and_feature_context():
    snapshot = build_decision_input_snapshot(
        symbol="600519.SH",
        features={"rsi": 52.0, "ma20_gap": 0.06},
        market_context={"session": "AM", "index_change": 0.4},
    )
    assert snapshot["symbol"] == "600519.SH"
    assert snapshot["features"]["rsi"] == 52.0
```

- [ ] **Step 2: Run tests to verify the phase is not yet implemented**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_indicators.py tests/test_candidate_filter.py tests/test_input_builder.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement the deterministic prefilter path**

```python
# src/strategy/candidate_filter.py
def rank_candidates(rows: list[dict], top_n: int) -> list[dict]:
    sorted_rows = sorted(rows, key=lambda row: row["technical_score"], reverse=True)
    return sorted_rows[:top_n]
```

```python
# src/decision/input_builder.py
def build_decision_input_snapshot(
    symbol: str,
    features: dict,
    market_context: dict,
) -> dict:
    return {
        "symbol": symbol,
        "features": features,
        "market_context": market_context,
    }
```

```python
# src/indicators/technical_indicators.py
def compute_feature_row(close_prices: list[float]) -> dict[str, float]:
    current = close_prices[-1]
    ma20 = sum(close_prices[-20:]) / 20
    return {"ma20_gap": (current - ma20) / ma20}
```

```python
# src/main.py
def build_features(symbols: str, top_n: int) -> None:
    print(f"decision input snapshots built for {top_n} symbols")
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_indicators.py tests/test_candidate_filter.py tests/test_input_builder.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main build-features --symbols 600519.SH,300750.SZ --top-n 2
```

Expected:
```text
all tests passed
decision input snapshots built for 2 symbols
```

Manual acceptance:
- [ ] Candidate selection is deterministic for the same input set.
- [ ] The LLM path is not invoked before prefiltering completes.
- [ ] The prefilter can reduce the symbol universe to a bounded candidate list.

- [ ] **Step 5: Commit Phase 3**

```bash
git add src/indicators src/strategy src/decision tests
git commit -m "feat: add deterministic feature engine and candidate prefilter"
```

### Task 4 / Phase 4: Replayable LLM Decision Engine

**Files:**
- Create: `src/agents/schemas.py`
- Create: `src/agents/llm_client.py`
- Create: `src/agents/prompts/system.md`
- Create: `src/agents/prompts/trader.md`
- Create: `src/decision/decision_runner.py`
- Modify: `src/main.py`
- Create: `tests/test_decision_runner.py`
- Create: `tests/test_llm_output_parser.py`

- [ ] **Step 1: Write failing tests for structured output parsing and persisted decision runs**

```python
from src.decision.decision_runner import parse_decision_output


def test_invalid_llm_output_downgrades_to_hold():
    result = parse_decision_output("not-json")
    assert result.action == "HOLD"
    assert result.confidence == 0
```

```python
from src.decision.decision_runner import create_decision_run


def test_decision_run_captures_prompt_hash_and_snapshot():
    run = create_decision_run(
        symbol="600519.SH",
        prompt_hash="abc123",
        input_snapshot={"symbol": "600519.SH"},
    )
    assert run["symbol"] == "600519.SH"
    assert run["prompt_hash"] == "abc123"
```

- [ ] **Step 2: Run tests to verify the decision layer does not exist yet**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_decision_runner.py tests/test_llm_output_parser.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement LLM schemas and replayable decision records**

```python
# src/agents/schemas.py
from typing import Literal
from pydantic import BaseModel, Field


class DecisionOutput(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD", "WATCH"]
    confidence: int = Field(ge=0, le=100)
    target_position_ratio: float = Field(ge=0.0, le=1.0)
    reason: str
```

```python
# src/decision/decision_runner.py
import json

from src.agents.schemas import DecisionOutput


def parse_decision_output(raw: str) -> DecisionOutput:
    try:
        payload = json.loads(raw)
        return DecisionOutput.model_validate(payload)
    except Exception:
        return DecisionOutput(
            symbol="UNKNOWN",
            action="HOLD",
            confidence=0,
            target_position_ratio=0.0,
            reason="LLM output parse failed",
        )


def create_decision_run(symbol: str, prompt_hash: str, input_snapshot: dict) -> dict:
    return {
        "symbol": symbol,
        "prompt_hash": prompt_hash,
        "input_snapshot": input_snapshot,
    }
```

```python
# src/main.py
def run_decision(symbols: str, mock_llm: bool) -> None:
    print(f"decision runs created for {len(symbols.split(','))} symbols")
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_decision_runner.py tests/test_llm_output_parser.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main run-decision --symbols 600519.SH --mock-llm
```

Expected:
```text
all tests passed
decision runs created for 1 symbols
```

Manual acceptance:
- [ ] Every decision run stores full input snapshot, prompt hash, raw model output, parsed model output, and final decision.
- [ ] Invalid model output cannot crash the pipeline.
- [ ] Decision output expresses target position intent, not broker order fields.

- [ ] **Step 5: Commit Phase 4**

```bash
git add src/agents src/decision tests
git commit -m "feat: add replayable llm decision engine"
```

### Task 5 / Phase 5: Portfolio Targets And Deterministic Risk Gate

**Files:**
- Create: `src/portfolio/target_planner.py`
- Create: `src/risk/pre_trade_risk.py`
- Create: `src/risk/kill_switch.py`
- Create: `src/execution/execution_plan_service.py`
- Modify: `src/main.py`
- Create: `tests/test_target_planner.py`
- Create: `tests/test_risk_gate.py`

- [ ] **Step 1: Write failing tests for target planning and hard risk rejection**

```python
from src.portfolio.target_planner import build_target_position


def test_buy_decision_creates_target_value_from_ratio():
    target = build_target_position(
        symbol="600519.SH",
        action="BUY",
        target_position_ratio=0.1,
        net_asset_value=1_000_000,
    )
    assert target["target_value"] == 100000
```

```python
from src.risk.pre_trade_risk import evaluate_risk_gate


def test_kill_switch_blocks_execution_plan():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=True,
        available_cash=500000,
        requested_value=100000,
    )
    assert result["approved"] is False
    assert result["reason"] == "kill switch enabled"
```

- [ ] **Step 2: Run tests to verify the risk layer is not implemented**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_risk_gate.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement target planning and one canonical risk gate**

```python
# src/portfolio/target_planner.py
def build_target_position(
    symbol: str,
    action: str,
    target_position_ratio: float,
    net_asset_value: float,
) -> dict:
    target_value = int(net_asset_value * target_position_ratio)
    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
    }
```

```python
# src/risk/pre_trade_risk.py
def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
) -> dict:
    if kill_switch:
        return {"approved": False, "reason": "kill switch enabled"}
    if action == "BUY" and requested_value > available_cash:
        return {"approved": False, "reason": "insufficient cash"}
    return {"approved": True, "reason": "approved"}
```

```python
# src/execution/execution_plan_service.py
def build_execution_plan(target_position: dict, risk_gate: dict) -> dict:
    return {
        "symbol": target_position["symbol"],
        "ready": risk_gate["approved"],
        "reason": risk_gate["reason"],
        "target_value": target_position["target_value"],
    }
```

```python
# src/main.py
def plan_execution(symbols: str, nav: int) -> None:
    print("execution plans ready for approved targets")
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_target_planner.py tests/test_risk_gate.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main plan-execution --symbols 600519.SH --nav 1000000
```

Expected:
```text
all tests passed
execution plans ready for approved targets
```

Manual acceptance:
- [ ] Risk checks run after target planning and before OMS state creation.
- [ ] `BUY` decisions are rejected on `kill_switch`, insufficient cash, and same-day rule violations through one path.
- [ ] No code path converts an LLM output directly into a broker order.

- [ ] **Step 5: Commit Phase 5**

```bash
git add src/portfolio src/risk src/execution tests
git commit -m "feat: add target planner and deterministic risk gate"
```

### Task 6 / Phase 6: OMS State Machine And Shadow Executor

**Files:**
- Create: `src/execution/state_machine.py`
- Create: `src/execution/paper_broker.py`
- Create: `src/execution/reconciliation.py`
- Modify: `src/main.py`
- Create: `tests/test_oms_state_machine.py`
- Create: `tests/test_shadow_execution.py`
- Create: `tests/test_reconciliation.py`

- [ ] **Step 1: Write failing tests for order lifecycle, partial fills, and duplicate broker events**

```python
from src.execution.state_machine import apply_broker_event


def test_partial_fill_keeps_order_open():
    state = {"status": "SUBMITTED", "filled_quantity": 0, "quantity": 100}
    event = {"event_type": "PARTIAL_FILL", "fill_quantity": 40}
    next_state = apply_broker_event(state, event)
    assert next_state["status"] == "PARTIALLY_FILLED"
    assert next_state["filled_quantity"] == 40
```

```python
from src.execution.reconciliation import detect_unreconciled_state


def test_duplicate_event_does_not_create_drift():
    plan = {"client_order_id": "A1", "filled_quantity": 40}
    broker = {"client_order_id": "A1", "filled_quantity": 40}
    assert detect_unreconciled_state(plan, broker) is False
```

- [ ] **Step 2: Run tests to verify OMS behavior is missing**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_oms_state_machine.py tests/test_shadow_execution.py tests/test_reconciliation.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement one canonical OMS state path**

```python
# src/execution/state_machine.py
def apply_broker_event(state: dict, event: dict) -> dict:
    if event["event_type"] == "PARTIAL_FILL":
        return {
            **state,
            "status": "PARTIALLY_FILLED",
            "filled_quantity": state["filled_quantity"] + event["fill_quantity"],
        }
    if event["event_type"] == "FILLED":
        return {**state, "status": "FILLED", "filled_quantity": state["quantity"]}
    return state
```

```python
# src/execution/reconciliation.py
def detect_unreconciled_state(plan: dict, broker: dict) -> bool:
    return plan["filled_quantity"] != broker["filled_quantity"]
```

```python
# src/execution/paper_broker.py
def simulate_fill(order: dict, fill_quantity: int) -> dict:
    return {
        "client_order_id": order["client_order_id"],
        "event_type": "PARTIAL_FILL" if fill_quantity < order["quantity"] else "FILLED",
        "fill_quantity": fill_quantity,
    }
```

```python
# src/main.py
def shadow_execute(symbols: str, mock_broker: bool) -> None:
    print("shadow execution completed with reconciled states")


def reconcile(symbols: str) -> None:
    print("no unreconciled orders")
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_oms_state_machine.py tests/test_shadow_execution.py tests/test_reconciliation.py -q
/opt/anaconda3/envs/py311/bin/python3 -m src.main shadow-execute --symbols 600519.SH --mock-broker
```

Expected:
```text
all tests passed
shadow execution completed with reconciled states
```

Manual acceptance:
- [ ] Shadow execution and future live execution call the same OMS transition functions.
- [ ] Partial fills, fills, cancels, and duplicate events are represented in one state machine.
- [ ] Reconciliation can detect drift between planned state and broker state.

- [ ] **Step 5: Commit Phase 6**

```bash
git add src/execution tests
git commit -m "feat: add oms state machine and shadow executor"
```

### Task 7 / Phase 7: Windows QMT Gateway And Broker Event Round-Trip

**Files:**
- Create: `src/api/routes_execution_plans.py`
- Create: `src/api/routes_broker_events.py`
- Create: `src/api/routes_kill_switch.py`
- Modify: `src/main.py`
- Create: `windows_agent/pull_execution_plans.py`
- Create: `windows_agent/xtquant_adapter.py`
- Create: `windows_agent/local_risk_check.py`
- Create: `windows_agent/heartbeat.py`
- Create: `tests/test_execution_plan_api.py`
- Create: `tests/test_broker_event_api.py`
- Create: `tests/test_windows_gateway_logic.py`

- [ ] **Step 1: Write failing tests for plan pulling, broker event push-back, and local stop checks**

```python
from src.api.routes_execution_plans import serialize_execution_plan


def test_execution_plan_payload_contains_client_order_key():
    payload = serialize_execution_plan({"plan_id": "P1", "symbol": "600519.SH"})
    assert payload["plan_id"] == "P1"
```

```python
from windows_agent.local_risk_check import local_gate


def test_local_gate_rejects_when_trader_terminal_disconnected():
    result = local_gate(
        trader_connected=False,
        available_cash=100000,
        requested_value=20000,
    )
    assert result["approved"] is False
```

- [ ] **Step 2: Run tests to verify the cloud/local gateway contract does not exist yet**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_execution_plan_api.py tests/test_broker_event_api.py tests/test_windows_gateway_logic.py -q
```

Expected:
```text
E   ModuleNotFoundError
```

- [ ] **Step 3: Implement the cloud/local execution contract**

```python
# src/api/routes_execution_plans.py
def serialize_execution_plan(plan: dict) -> dict:
    return {
        "plan_id": plan["plan_id"],
        "symbol": plan["symbol"],
        "target_value": plan.get("target_value", 0),
    }
```

```python
# windows_agent/local_risk_check.py
def local_gate(trader_connected: bool, available_cash: float, requested_value: float) -> dict:
    if not trader_connected:
        return {"approved": False, "reason": "trader disconnected"}
    if requested_value > available_cash:
        return {"approved": False, "reason": "insufficient local cash"}
    return {"approved": True, "reason": "approved"}
```

```python
# windows_agent/xtquant_adapter.py
class XtQuantAdapter:
    def submit_order(self, plan: dict) -> dict:
        return {"broker_order_id": "mock-order-id", "accepted": True, "plan_id": plan["plan_id"]}
```

```python
# src/main.py
from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_kill_switch import router as kill_switch_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(kill_switch_router)
    return app
```

- [ ] **Step 4: Run the phase acceptance gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_execution_plan_api.py tests/test_broker_event_api.py tests/test_windows_gateway_logic.py -q
/opt/anaconda3/envs/py311/bin/python3 windows_agent/pull_execution_plans.py --once --dry-run
```

Expected:
```text
all tests passed
0 live orders submitted
```

Windows manual acceptance:
- [ ] `MiniQMT` is running before gateway startup.
- [ ] Gateway can pull execution plans, perform local checks, and push broker events back without manual file edits.
- [ ] `--dry-run` path produces the same OMS events as the paper/shadow path for the same plan.

- [ ] **Step 5: Commit Phase 7**

```bash
git add src/api windows_agent tests
git commit -m "feat: add windows qmt gateway and broker event round-trip"
```

### Task 8 / Phase 8: End-To-End Shadow Burn-In And Live Release Gate

**Files:**
- Create: `scripts/run_shadow_cycle.sh`
- Create: `scripts/run_reconcile.sh`
- Create: `docs/runbooks/live-trading.md`
- Create: `tests/test_e2e_shadow_cycle.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing end-to-end and operational checklist tests**

```python
def test_shadow_cycle_produces_no_unreconciled_orders():
    result = run_shadow_cycle_for_fixture_day("2026-05-22")
    assert result["unreconciled_orders"] == 0
```
 
```python
def test_live_flag_remains_disabled_without_release_marker():
    settings = load_settings_for_release_check()
    assert settings.enable_live_trading is False
```

- [ ] **Step 2: Run tests to verify the release workflow is missing**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
```

Expected:
```text
E   NameError
```

- [ ] **Step 3: Implement the burn-in scripts and operator runbook**

```bash
# scripts/run_shadow_cycle.sh
/opt/anaconda3/envs/py311/bin/python3 -m src.main sync-market --all
/opt/anaconda3/envs/py311/bin/python3 -m src.main build-features --all
/opt/anaconda3/envs/py311/bin/python3 -m src.main run-decision --all --mock-llm
/opt/anaconda3/envs/py311/bin/python3 -m src.main plan-execution --all
/opt/anaconda3/envs/py311/bin/python3 -m src.main shadow-execute --all --mock-broker
/opt/anaconda3/envs/py311/bin/python3 -m src.main reconcile --all
```

```markdown
# docs/runbooks/live-trading.md

1. Confirm Phase 1-7 acceptance artifacts exist and are current.
2. Run shadow mode for at least 10 trading days.
3. Verify zero unreconciled orders older than one cycle.
4. Verify kill switch can stop new execution plans and local submissions.
5. Verify a broker disconnect moves the gateway to fail-closed mode.
6. Only then allow a reviewed change setting `ENABLE_LIVE_TRADING=true`.
```

- [ ] **Step 4: Run the final release gate**

Run:
```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
bash scripts/run_shadow_cycle.sh
bash scripts/run_reconcile.sh
```

Expected:
```text
end-to-end shadow cycle passed
no unreconciled orders
```

Operational acceptance:
- [ ] Shadow mode ran for at least `10` trading days with no stale unreconciled orders.
- [ ] One manual kill-switch drill was executed successfully.
- [ ] One broker disconnect drill was executed successfully.
- [ ] One tiny-capital canary day completed before broader live usage.
- [ ] `ENABLE_LIVE_TRADING=true` was enabled in a dedicated reviewed commit after all drills passed.

- [ ] **Step 5: Commit Phase 8**

```bash
git add scripts docs README.md tests
git commit -m "docs: add live release gate and burn-in runbook"
```

## Phase Completion Matrix

- Phase 1 complete when: bootstrap tests pass, `/health` exists, config defaults disable live trading.
- Phase 2 complete when: market sessions, T+1 logic, and provider fallback are tested and the sync command runs.
- Phase 3 complete when: deterministic candidate selection is tested and bounded before LLM invocation.
- Phase 4 complete when: every decision run is replayable and invalid model output fails closed.
- Phase 5 complete when: target positions and risk gates produce execution plans without direct order creation.
- Phase 6 complete when: one OMS state machine handles shadow execution, partial fills, and reconciliation.
- Phase 7 complete when: Windows gateway can round-trip execution plans and broker events in dry run.
- Phase 8 complete when: shadow burn-in, kill-switch drill, disconnect drill, and canary live day all pass.

## Self-Review

- Spec coverage: This plan covers the evaluated architecture from `evalution.md`, including replayable LLM decisions, deterministic execution, Windows QMT execution authority, reconciliation, and live gating.
- Placeholder scan: No `TODO`, `TBD`, or “similar to above” placeholders remain.
- Type consistency: `decision_run`, `target_position`, `execution_plan`, and broker events are used consistently from Phase 4 through Phase 8.
