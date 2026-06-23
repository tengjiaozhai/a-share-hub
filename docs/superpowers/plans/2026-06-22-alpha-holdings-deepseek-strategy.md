# Holdings Analysis DeepSeek Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the holdings page's rule-only recommendation with an auditable, position-aware pipeline that builds a deterministic market snapshot, asks DeepSeek for a Research Manager plan and Trader proposal, applies hard risk rules, persists the complete run, and displays one final `ADD / HOLD / REDUCE / EXIT` decision.

**Architecture:** Keep `POST /api/v1/alpha/portfolio/report` as the canonical report endpoint and keep the existing holdings CRUD path unchanged. The report service will build facts first, call two structured LLM stages, pass their output through a deterministic risk engine, save one analysis-run record, and return that same record shape to the dashboard. Remove the existing shadow-opinion and rule-recommendation path in the same change; do not keep dual recommendations or silently replace DeepSeek failures with mock decisions.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, httpx, pandas, AkShare/Tencent market data, yfinance, vanilla JavaScript, pytest.

---

## Scope And Locked Decisions

- The feature analyzes manually recorded A-share and US-stock holdings. It does not place orders.
- Holdings entries and weighted-average cost remain authoritative in `alpha_holdings_entries` and `alpha_positions`.
- DeepSeek interprets supplied evidence. It never calculates P&L, moving averages, stop-loss triggers, or position limits.
- The Research Manager emits `BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL`.
- The Trader emits `BUY / HOLD / SELL`.
- The deterministic risk stage emits the only user-facing action: `ADD / HOLD / REDUCE / EXIT`.
- An LLM transport, JSON, or schema failure produces `status="failed"`, `research=null`, `trader=null`, `risk=null`, and a visible error. It must not produce a mock `HOLD`.
- News is not currently available through a repository-owned provider. The snapshot records `news.status="unavailable"`; prompts must lower confidence and must not invent news evidence.
- US fundamentals use the existing `YahooProvider.get_fundamental`. A-share fundamentals initially use fields already returned by the Tencent quote path, such as `pe_ratio`. Missing fundamental fields remain explicit data gaps.
- Existing `include_shadow`, `shadow`, and rule-only `recommendation` fields are removed from the report request, response, backend implementation, frontend controls, and tests in the same rollout.

## File Responsibility Map

### Create

- `src/alpha/analysis_models.py`: Pydantic contracts for snapshot, research plan, trader proposal, risk decision, and persisted run response.
- `src/alpha/analysis_snapshot.py`: A-share/US market-data loading and deterministic feature/P&L snapshot construction.
- `src/alpha/analysis_agents.py`: Research Manager and Trader prompts plus structured DeepSeek invocation.
- `src/alpha/analysis_risk.py`: Pure deterministic mapping from facts and LLM proposals to the final action.
- `alembic/versions/20260622_000020_add_alpha_analysis_runs.py`: `alpha_analysis_runs` audit table.
- `tests/test_alpha_analysis_models.py`: Schema boundary tests.
- `tests/test_alpha_analysis_snapshot.py`: Snapshot and data-quality tests.
- `tests/test_alpha_analysis_agents.py`: Prompt handoff and structured-output tests.
- `tests/test_alpha_analysis_risk.py`: Risk priority and action tests.
- `tests/test_alpha_analysis_runs.py`: Store persistence and tenant-isolation tests.

### Modify

- `src/agents/llm_client.py`: Add a strict structured JSON method that raises typed errors; leave the workbench's existing `generate` caller behavior outside this feature's scope.
- `src/storage/models.py`: Add `AlphaAnalysisRunRow`.
- `src/storage/runtime_store.py`: Insert, fetch, and list analysis runs scoped by `user_id`.
- `src/alpha/report_service.py`: Become the single orchestration path and remove old shadow/rule recommendation builders.
- `src/api/routes_alpha.py`: Inject settings/LLM dependencies, normalize the new request, return report history, and remove `include_shadow`.
- `src/api/dashboard_page/partials/view_alpha.html`: Remove the shadow toggle and add analysis status/history containers.
- `src/api/dashboard_page/scripts/alpha.js`: Render Research, Trader, Risk, data quality, exact close-time P&L, and explicit failures.
- `src/api/dashboard_page/styles/alpha.css`: Style decision status and expandable evidence without changing other dashboard tabs.
- `tests/test_llm_client.py`: Strict JSON success/failure behavior.
- `tests/test_alpha_portfolio_report_service.py`: Replace shadow/recommendation tests with end-to-end orchestration tests.
- `tests/test_alpha_routes.py`: Lock the new API request/response and history contracts.
- `tests/test_dashboard_alpha_tab.py`: Lock visible holdings-analysis controls.
- `tests/test_dashboard_page_contract.py`: Forbid the removed shadow path and require the new decision sections.
- `README.md`: Document the analysis pipeline, DeepSeek requirement, data limitations, and non-execution boundary.

## Task 1: Define Canonical Analysis Contracts

**Files:**
- Create: `src/alpha/analysis_models.py`
- Create: `tests/test_alpha_analysis_models.py`

- [ ] **Step 1: Write failing schema tests**

```python
import pytest
from pydantic import ValidationError

from src.alpha.analysis_models import ResearchPlan, RiskDecision, TraderProposal


def test_research_plan_accepts_only_five_ratings():
    plan = ResearchPlan(
        rating="OVERWEIGHT",
        thesis="趋势保持，但估值证据有限",
        technical_view="收盘价位于 MA20 与 MA60 上方",
        fundamental_view="仅有 PE 数据",
        sentiment_view="新闻数据不可用",
        catalysts=["成交量确认"],
        risks=["新闻数据缺失"],
        confidence=0.68,
        data_gaps=["news"],
    )
    assert plan.rating == "OVERWEIGHT"

    with pytest.raises(ValidationError):
        ResearchPlan(
            rating="STRONG_BUY",
            thesis="invalid",
            technical_view="invalid",
            fundamental_view="invalid",
            sentiment_view="invalid",
            catalysts=[],
            risks=[],
            confidence=0.5,
            data_gaps=[],
        )


def test_trader_and_risk_actions_have_distinct_contracts():
    proposal = TraderProposal(
        action="BUY",
        reasoning="趋势回踩后重新确认",
        entry_low=16.0,
        entry_high=16.8,
        stop_loss=15.0,
        take_profit=19.0,
        position_ratio=0.1,
    )
    decision = RiskDecision(
        action="ADD",
        reason="研究和交易方向一致，且未触发硬限制",
        triggered_rules=["trend_pullback_confirmed"],
        approved_position_ratio=0.1,
    )
    assert proposal.action == "BUY"
    assert decision.action == "ADD"
```

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_models.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src.alpha.analysis_models'`.

- [ ] **Step 3: Add the complete Pydantic contracts**

```python
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ResearchRating = Literal["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
TraderAction = Literal["BUY", "HOLD", "SELL"]
FinalAction = Literal["ADD", "HOLD", "REDUCE", "EXIT"]


class AnalysisSnapshot(BaseModel):
    symbol: str
    market: Literal["a", "us"]
    currency: Literal["CNY", "USD"]
    as_of: str
    quantity: float = Field(ge=0)
    weighted_avg_cost: float = Field(ge=0)
    close: float = Field(gt=0)
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_ratio: float
    position_ratio: float = Field(ge=0)
    stop_loss_ratio: float
    take_profit_ratio: float
    technical: dict
    fundamentals: dict
    news: dict
    data_quality: dict


class ResearchPlan(BaseModel):
    rating: ResearchRating
    thesis: str = Field(min_length=1)
    technical_view: str = Field(min_length=1)
    fundamental_view: str = Field(min_length=1)
    sentiment_view: str = Field(min_length=1)
    catalysts: list[str]
    risks: list[str]
    confidence: float = Field(ge=0, le=1)
    data_gaps: list[str]


class TraderProposal(BaseModel):
    action: TraderAction
    reasoning: str = Field(min_length=1)
    entry_low: float | None = Field(default=None, gt=0)
    entry_high: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    position_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.entry_low is not None and self.entry_high is not None and self.entry_low > self.entry_high:
            raise ValueError("entry_low must be <= entry_high")
        return self


class RiskDecision(BaseModel):
    action: FinalAction
    reason: str = Field(min_length=1)
    triggered_rules: list[str]
    approved_position_ratio: float = Field(ge=0, le=1)


class AnalysisRunResult(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    snapshot: AnalysisSnapshot | None
    research: ResearchPlan | None
    trader: TraderProposal | None
    risk: RiskDecision | None
    model_name: str
    error: str | None
    created_at: str
```

- [ ] **Step 4: Run contract tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_models.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the contracts**

```bash
git add src/alpha/analysis_models.py tests/test_alpha_analysis_models.py
git commit -m "feat(alpha): define holdings analysis contracts"
```

**Success standard:** Invalid ratings, actions, confidence values, position ratios, and reversed entry ranges fail Pydantic validation; valid Research, Trader, and Risk objects serialize to stable JSON without overlapping action vocabularies.

## Task 2: Add Strict DeepSeek JSON Invocation

**Files:**
- Modify: `src/agents/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Add failing strict-mode tests**

```python
import pytest

from src.agents.llm_client import LLMClient, LLMGenerationError
from src.core.config import Settings


def test_generate_json_requires_api_key():
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key=""))
    with pytest.raises(LLMGenerationError, match="LLM_API_KEY"):
        client.generate_json(system_prompt="system", user_prompt="user")


def test_generate_json_rejects_non_json(monkeypatch):
    monkeypatch.setattr(
        "src.agents.llm_client.LLMClient._post_chat",
        lambda self, payload: "not-json",
    )
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key="test-key"))
    with pytest.raises(LLMGenerationError, match="invalid JSON"):
        client.generate_json(system_prompt="system", user_prompt="user")
```

- [ ] **Step 2: Verify strict-mode tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client.py -q
```

Expected: fails because `LLMGenerationError` and `generate_json` do not exist.

- [ ] **Step 3: Implement a strict method without changing existing workbench callers**

Add this API to `src/agents/llm_client.py` and route both HTTP calls through `_post_chat`:

```python
class LLMGenerationError(RuntimeError):
    pass


def _post_chat(self, payload: dict) -> str:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"])


def generate_json(
    self,
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> dict:
    if self.provider == "mock" or not self.api_key:
        raise LLMGenerationError("DeepSeek analysis requires LLM_API_KEY")
    payload = {
        "model": self.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        parsed = json.loads(self._post_chat(payload))
    except json.JSONDecodeError as exc:
        raise LLMGenerationError("DeepSeek returned invalid JSON") from exc
    except (httpx.HTTPError, KeyError, TypeError) as exc:
        raise LLMGenerationError(f"DeepSeek request failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMGenerationError("DeepSeek JSON response must be an object")
    return parsed
```

- [ ] **Step 4: Run all LLM client tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client.py tests/test_shadow_run_service.py -q
```

Expected: strict holdings-analysis tests pass and existing workbench decision tests remain green.

- [ ] **Step 5: Commit strict DeepSeek support**

```bash
git add src/agents/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): add strict structured DeepSeek calls"
```

**Success standard:** The holdings-analysis call returns a JSON object on success and raises `LLMGenerationError` for a missing key, transport error, malformed response, or non-object JSON; no strict-path failure returns mock investment advice.

## Task 3: Build The Deterministic Position And Market Snapshot

**Files:**
- Create: `src/alpha/analysis_snapshot.py`
- Create: `tests/test_alpha_analysis_snapshot.py`
- Reuse: `src/indicators/technical_indicators.py`
- Reuse: `src/data/providers/akshare_provider.py`
- Reuse: `src/us_stock/yahoo_provider.py`

- [ ] **Step 1: Write failing snapshot tests with injected market loaders**

```python
import pytest
from datetime import date, timedelta

from src.alpha.analysis_snapshot import AnalysisSnapshotBuilder


def test_snapshot_uses_weighted_cost_and_computed_features():
    start = date(2026, 3, 1)
    bars = [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "close": 10.0 + index * 0.1,
            "volume": 1000 + index,
        }
        for index in range(61)
    ]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok", "pe_ratio": 18.2},
    )
    snapshot = builder.build(
        symbol="600703.SH",
        lots=[
            {"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
            {"buy_price": 14.0, "quantity": 200, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
        ],
        portfolio_market_value=10_000.0,
    )

    assert snapshot.weighted_avg_cost == pytest.approx(13.333333)
    assert snapshot.close == pytest.approx(16.0)
    assert snapshot.unrealized_pnl == pytest.approx(800.0)
    assert snapshot.technical["bar_count"] == 61
    assert snapshot.technical["ma20"] > snapshot.technical["ma60"]
    assert isinstance(snapshot.technical["reclaimed_ma20"], bool)
    assert snapshot.news == {"status": "unavailable", "items": []}


def test_snapshot_rejects_missing_close():
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: [],
        fundamental_loader=lambda symbol: {"status": "unavailable"},
    )
    with pytest.raises(ValueError, match="no closing price"):
        builder.build(
            symbol="MSFT.US",
            lots=[{"buy_price": 420.0, "quantity": 2.0}],
            portfolio_market_value=840.0,
        )
```

- [ ] **Step 2: Verify snapshot tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py -q
```

Expected: fails because `AnalysisSnapshotBuilder` does not exist.

- [ ] **Step 3: Implement the snapshot builder**

The builder must:

```python
from collections.abc import Callable

from src.alpha.analysis_models import AnalysisSnapshot
from src.indicators.technical_indicators import compute_features_from_bars


def _trend_confirmation(bars: list[dict]) -> dict:
    closes = [float(row["close"]) for row in bars]
    if len(closes) < 61:
        return {"ma20": 0.0, "ma60": 0.0, "reclaimed_ma20": False}
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    previous_ma20 = sum(closes[-21:-1]) / 20
    reclaimed = closes[-2] <= previous_ma20 and closes[-1] > ma20
    return {
        "ma20": round(ma20, 6),
        "ma60": round(ma60, 6),
        "reclaimed_ma20": reclaimed,
    }


class AnalysisSnapshotBuilder:
    def __init__(
        self,
        history_loader: Callable[[str], list[dict]],
        fundamental_loader: Callable[[str], dict],
    ) -> None:
        self._history_loader = history_loader
        self._fundamental_loader = fundamental_loader

    def build(self, *, symbol: str, lots: list[dict], portfolio_market_value: float) -> AnalysisSnapshot:
        bars = self._history_loader(symbol)
        if not bars or float(bars[-1].get("close", 0) or 0) <= 0:
            raise ValueError(f"no closing price for {symbol}")
        quantity = sum(float(lot["quantity"]) for lot in lots)
        total_cost = sum(float(lot["buy_price"]) * float(lot["quantity"]) for lot in lots)
        weighted_cost = total_cost / quantity
        close = float(bars[-1]["close"])
        market_value = close * quantity
        pnl = market_value - total_cost
        features = compute_features_from_bars(bars)
        features.update(_trend_confirmation(bars))
        missing = []
        if features["bar_count"] < 61:
            missing.append("technical_history")
        fundamentals = self._fundamental_loader(symbol)
        if fundamentals.get("status") != "ok":
            missing.append("fundamentals")
        missing.append("news")
        return AnalysisSnapshot(
            symbol=symbol,
            market="us" if symbol.endswith(".US") else "a",
            currency="USD" if symbol.endswith(".US") else "CNY",
            as_of=str(bars[-1].get("date") or bars[-1].get("timestamp"))[:10],
            quantity=quantity,
            weighted_avg_cost=round(weighted_cost, 6),
            close=close,
            market_value=market_value,
            unrealized_pnl=pnl,
            unrealized_pnl_ratio=pnl / total_cost,
            position_ratio=market_value / portfolio_market_value if portfolio_market_value > 0 else 1.0,
            stop_loss_ratio=float(lots[-1].get("stop_loss_ratio", -0.08)),
            take_profit_ratio=float(lots[-1].get("take_profit_ratio", 0.20)),
            technical=features,
            fundamentals=fundamentals,
            news={"status": "unavailable", "items": []},
            data_quality={"status": "partial" if missing else "complete", "missing": missing},
        )
```

Production loaders must request at least 120 calendar days, normalize A-share pandas rows into dictionaries, normalize US `USKline` rows into dictionaries, and use `YahooProvider.get_fundamental` for `.US` symbols. Do not catch market-data failures inside `build`; the report service owns item-level failure reporting.

- [ ] **Step 4: Run snapshot and indicator tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py tests/test_indicators.py tests/test_akshare_history.py tests/us_stock/test_cache.py -q
```

Expected: all tests pass; snapshots use computed facts and report unavailable evidence explicitly.

- [ ] **Step 5: Commit the snapshot builder**

```bash
git add src/alpha/analysis_snapshot.py tests/test_alpha_analysis_snapshot.py
git commit -m "feat(alpha): build auditable holdings snapshots"
```

**Success standard:** Two lots produce the exact weighted cost and close-based P&L expected by arithmetic; technical values come from repository indicators; A-share and US snapshots identify currency correctly; missing prices fail the item; unavailable news/fundamentals appear in `data_quality.missing` rather than fabricated text.

## Task 4: Implement Research Manager And Trader Handoff

**Files:**
- Create: `src/alpha/analysis_agents.py`
- Create: `tests/test_alpha_analysis_agents.py`

- [ ] **Step 1: Write failing handoff tests**

```python
from src.alpha.analysis_agents import ResearchManager, Trader
from src.alpha.analysis_models import AnalysisSnapshot


class FakeStructuredLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        symbol="600703.SH",
        market="a",
        currency="CNY",
        as_of="2026-06-22",
        quantity=300,
        weighted_avg_cost=13.333333,
        close=16.0,
        market_value=4800.0,
        unrealized_pnl=800.0,
        unrealized_pnl_ratio=0.2,
        position_ratio=0.08,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={"ma20": 15.7, "ma60": 14.8, "reclaimed_ma20": True},
        fundamentals={"status": "ok", "pe_ratio": 18.2},
        news={"status": "unavailable", "items": []},
        data_quality={"status": "partial", "missing": ["news"]},
    )


def test_trader_receives_research_plan_and_snapshot():
    snapshot = _snapshot()
    llm = FakeStructuredLLM([
        {
            "rating": "OVERWEIGHT",
            "thesis": "趋势保持",
            "technical_view": "MA20 高于 MA60",
            "fundamental_view": "估值数据有限",
            "sentiment_view": "新闻不可用",
            "catalysts": ["回踩确认"],
            "risks": ["新闻缺失"],
            "confidence": 0.66,
            "data_gaps": ["news"],
        },
        {
            "action": "BUY",
            "reasoning": "研究方向偏多且位置未追高",
            "entry_low": 15.8,
            "entry_high": 16.2,
            "stop_loss": 15.0,
            "take_profit": 19.0,
            "position_ratio": 0.1,
        },
    ])
    research = ResearchManager(llm).analyze(snapshot)
    proposal = Trader(llm).propose(snapshot, research)

    assert proposal.action == "BUY"
    assert '"rating": "OVERWEIGHT"' in llm.calls[1]["user_prompt"]
    assert '"weighted_avg_cost"' in llm.calls[1]["user_prompt"]
```

- [ ] **Step 2: Verify agent tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_agents.py -q
```

Expected: fails because the agent module does not exist.

- [ ] **Step 3: Implement schema-validated agents**

```python
import json

from pydantic import ValidationError

from src.agents.llm_client import LLMGenerationError
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


class AnalysisAgentError(RuntimeError):
    pass


class ResearchManager:
    SYSTEM_PROMPT = (
        "你是持仓研究经理。只能使用输入 JSON 中的证据。"
        "输出 BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL 五档评级。"
        "数据缺失必须写入 data_gaps 并降低 confidence，不得补写未提供的新闻或财务事实。"
        "只输出合法 JSON。"
    )

    def __init__(self, llm) -> None:
        self._llm = llm

    def analyze(self, snapshot: AnalysisSnapshot) -> ResearchPlan:
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=snapshot.model_dump_json(),
                temperature=0.2,
                max_tokens=1400,
            )
            return ResearchPlan.model_validate(payload)
        except (LLMGenerationError, ValidationError) as exc:
            raise AnalysisAgentError(f"research manager failed: {exc}") from exc


class Trader:
    SYSTEM_PROMPT = (
        "你是交易员。不要重新研究公司，只把研究计划和当前持仓转换为 BUY/HOLD/SELL。"
        "给出入场区间、止损、止盈和建议仓位。已有持仓时 BUY 表示建议加仓。"
        "只输出合法 JSON。"
    )

    def __init__(self, llm) -> None:
        self._llm = llm

    def propose(self, snapshot: AnalysisSnapshot, research: ResearchPlan) -> TraderProposal:
        context = {"snapshot": snapshot.model_dump(), "research": research.model_dump()}
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True),
                temperature=0.1,
                max_tokens=1000,
            )
            return TraderProposal.model_validate(payload)
        except (LLMGenerationError, ValidationError) as exc:
            raise AnalysisAgentError(f"trader failed: {exc}") from exc
```

- [ ] **Step 4: Run agent contract tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_agents.py tests/test_alpha_analysis_models.py tests/test_llm_client.py -q
```

Expected: all tests pass; the Trader prompt contains the exact validated Research Manager result and deterministic snapshot.

- [ ] **Step 5: Commit the two-stage analysis**

```bash
git add src/alpha/analysis_agents.py tests/test_alpha_analysis_agents.py
git commit -m "feat(alpha): add research manager and trader stages"
```

**Success standard:** Research output is validated before Trader execution; Trader receives the Research plan and holdings snapshot; malformed output stops that symbol's analysis with `AnalysisAgentError`; prompts explicitly prohibit invented evidence.

## Task 5: Implement Deterministic Risk Priority

**Files:**
- Create: `src/alpha/analysis_risk.py`
- Create: `tests/test_alpha_analysis_risk.py`

- [ ] **Step 1: Write one failing test per priority rule**

```python
from src.alpha.analysis_risk import evaluate_risk
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


def _snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        symbol="600703.SH",
        market="a",
        currency="CNY",
        as_of="2026-06-22",
        quantity=300,
        weighted_avg_cost=13.333333,
        close=16.0,
        market_value=4800.0,
        unrealized_pnl=800.0,
        unrealized_pnl_ratio=0.06,
        position_ratio=0.08,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={
            "ma20": 15.7,
            "ma60": 14.8,
            "ma20_gap": 0.02,
            "ma60_gap": 0.08,
            "volume_ratio_20": 1.2,
            "bar_count": 61,
            "reclaimed_ma20": True,
        },
        fundamentals={"status": "ok", "pe_ratio": 18.2},
        news={"status": "unavailable", "items": []},
        data_quality={"status": "partial", "missing": ["news"]},
    )


def _research() -> ResearchPlan:
    return ResearchPlan(
        rating="OVERWEIGHT",
        thesis="上涨趋势保持",
        technical_view="回踩 MA20 后重新站稳",
        fundamental_view="估值数据有限",
        sentiment_view="新闻不可用",
        catalysts=["成交量确认"],
        risks=["新闻缺失"],
        confidence=0.66,
        data_gaps=["news"],
    )


def _proposal() -> TraderProposal:
    return TraderProposal(
        action="BUY",
        reasoning="研究方向偏多且位置未追高",
        entry_low=15.8,
        entry_high=16.2,
        stop_loss=15.0,
        take_profit=19.0,
        position_ratio=0.1,
    )


def test_stop_loss_forces_exit():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    breached = snapshot.model_copy(update={"unrealized_pnl_ratio": -0.09})
    decision = evaluate_risk(breached, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "EXIT"
    assert decision.triggered_rules == ["stop_loss_breached"]


def test_take_profit_reduces_before_llm_buy():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    profitable = snapshot.model_copy(update={"unrealized_pnl_ratio": 0.22})
    decision = evaluate_risk(profitable, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "REDUCE"


def test_add_requires_trend_pullback_and_capacity():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    eligible = snapshot.model_copy(update={
        "position_ratio": 0.08,
        "technical": {
            "ma20": 15.7,
            "ma60": 14.8,
            "ma20_gap": 0.02,
            "ma60_gap": 0.08,
            "volume_ratio_20": 1.2,
            "bar_count": 61,
            "reclaimed_ma20": True,
        },
    })
    decision = evaluate_risk(eligible, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "ADD"


def test_missing_technical_history_blocks_add():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    partial = snapshot.model_copy(update={
        "data_quality": {"status": "partial", "missing": ["technical_history", "news"]},
    })
    decision = evaluate_risk(partial, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "HOLD"
```

- [ ] **Step 2: Verify risk tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_risk.py -q
```

Expected: fails because `evaluate_risk` does not exist.

- [ ] **Step 3: Implement ordered, pure risk rules**

```python
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, RiskDecision, TraderProposal


def evaluate_risk(
    snapshot: AnalysisSnapshot,
    research: ResearchPlan,
    trader: TraderProposal,
    *,
    max_position_ratio: float,
) -> RiskDecision:
    pnl_ratio = snapshot.unrealized_pnl_ratio
    if pnl_ratio <= snapshot.stop_loss_ratio:
        return RiskDecision(
            action="EXIT",
            reason="收盘浮亏已达到持仓止损线",
            triggered_rules=["stop_loss_breached"],
            approved_position_ratio=0,
        )
    if research.rating == "SELL":
        return RiskDecision(
            action="EXIT",
            reason="研究结论为 SELL，原持仓逻辑已被否定",
            triggered_rules=["research_sell"],
            approved_position_ratio=0,
        )
    if pnl_ratio >= snapshot.take_profit_ratio:
        return RiskDecision(
            action="REDUCE",
            reason="收盘浮盈已达到持仓止盈线",
            triggered_rules=["take_profit_reached"],
            approved_position_ratio=max(0, snapshot.position_ratio / 2),
        )
    if trader.action == "SELL" or research.rating == "UNDERWEIGHT":
        return RiskDecision(
            action="REDUCE",
            reason="交易建议偏空或研究评级为 UNDERWEIGHT",
            triggered_rules=["directional_reduce"],
            approved_position_ratio=max(0, snapshot.position_ratio / 2),
        )
    missing = set(snapshot.data_quality.get("missing", []))
    if "technical_history" in missing:
        return RiskDecision(
            action="HOLD",
            reason="技术历史不足，禁止新增风险敞口",
            triggered_rules=["insufficient_technical_history"],
            approved_position_ratio=snapshot.position_ratio,
        )
    if snapshot.position_ratio >= max_position_ratio:
        return RiskDecision(
            action="HOLD",
            reason="当前持仓比例已达到单票上限",
            triggered_rules=["position_limit_reached"],
            approved_position_ratio=snapshot.position_ratio,
        )
    technical = snapshot.technical
    trend_ok = (
        snapshot.close > technical.get("ma20", 0) > technical.get("ma60", 0)
        and technical.get("reclaimed_ma20") is True
    )
    not_extended = technical.get("ma20_gap", 0) <= 0.05
    volume_ok = technical.get("volume_ratio_20", 0) >= 1.0
    if research.rating in {"BUY", "OVERWEIGHT"} and trader.action == "BUY" and trend_ok and not_extended and volume_ok:
        approved = min(max_position_ratio, max(snapshot.position_ratio, trader.position_ratio))
        return RiskDecision(
            action="ADD",
            reason="研究和交易方向一致，趋势回踩与成交量条件满足",
            triggered_rules=["trend_pullback_confirmed"],
            approved_position_ratio=approved,
        )
    return RiskDecision(
        action="HOLD",
        reason="未满足减仓或加仓的完整条件",
        triggered_rules=["no_action_trigger"],
        approved_position_ratio=snapshot.position_ratio,
    )
```

- [ ] **Step 4: Run risk and schema tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_risk.py tests/test_alpha_analysis_models.py -q
```

Expected: all rules pass in priority order; stop loss cannot be overridden by a bullish LLM result.

- [ ] **Step 5: Commit deterministic risk logic**

```bash
git add src/alpha/analysis_risk.py tests/test_alpha_analysis_risk.py
git commit -m "feat(alpha): enforce deterministic holdings risk rules"
```

**Success standard:** Stop loss has highest priority; `SELL` research forces exit; take profit and underweight signals reduce; insufficient history and position limits block adds; `ADD` requires all research, Trader, trend, distance, volume, and capacity conditions.

## Task 6: Persist One Auditable Analysis Run

**Files:**
- Create: `alembic/versions/20260622_000020_add_alpha_analysis_runs.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Create: `tests/test_alpha_analysis_runs.py`
- Modify: `tests/test_runtime_schema_bootstrap.py`

- [ ] **Step 1: Write failing store and tenant-isolation tests**

```python
from src.core.tenant import TenantContext
from src.storage.runtime_store import RuntimeStore


def test_analysis_runs_round_trip_and_are_user_isolated(pg_engine):
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    bob = RuntimeStore(pg_engine, TenantContext("bob"))
    run_id = alice.insert_alpha_analysis_run(
        symbol="600703.SH",
        status="completed",
        snapshot={"close": 16.0},
        research={"rating": "OVERWEIGHT"},
        trader={"action": "BUY"},
        risk={"action": "ADD"},
        model_name="deepseek-v4-pro",
        error=None,
    )

    assert alice.get_alpha_analysis_run(run_id)["risk"] == {"action": "ADD"}
    assert bob.get_alpha_analysis_run(run_id) is None
    assert bob.list_alpha_analysis_runs(symbol="600703.SH") == []
```

- [ ] **Step 2: Verify persistence tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_runs.py -q
```

Expected: fails because the model and store methods do not exist.

- [ ] **Step 3: Add migration and SQLAlchemy model**

The migration must use revision `20260622_000020`, down revision `20260622_000019`, and create:

```python
op.create_table(
    "alpha_analysis_runs",
    sa.Column("run_id", sa.String(length=64), primary_key=True),
    sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("symbol", sa.String(length=32), nullable=False, index=True),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("snapshot_json", sa.Text(), nullable=True),
    sa.Column("research_json", sa.Text(), nullable=True),
    sa.Column("trader_json", sa.Text(), nullable=True),
    sa.Column("risk_json", sa.Text(), nullable=True),
    sa.Column("model_name", sa.String(length=64), nullable=False),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
)
```

Define the matching `AlphaAnalysisRunRow` in `src/storage/models.py`. `downgrade()` drops only `alpha_analysis_runs`.

- [ ] **Step 4: Add user-scoped store methods**

Implement `insert_alpha_analysis_run`, `get_alpha_analysis_run`, and `list_alpha_analysis_runs`. Accept `snapshot: dict | None`; serialize present dicts with `json.dumps(..., ensure_ascii=False, sort_keys=True)` and preserve absent sections as SQL `NULL`. Deserialize present JSON on read. Every query must include `AlphaAnalysisRunRow.user_id == self.user_id`; listing must sort by `created_at.desc()` and accept `symbol: str | None` and `limit: int = 20`.

- [ ] **Step 5: Verify migration and store behavior**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m alembic heads
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_runs.py tests/test_runtime_schema_bootstrap.py tests/test_user_isolation.py -q
```

Expected: Alembic reports only `20260622_000020 (head)`; all persistence and tenant tests pass.

- [ ] **Step 6: Commit the audit store**

```bash
git add alembic/versions/20260622_000020_add_alpha_analysis_runs.py src/storage/models.py src/storage/runtime_store.py tests/test_alpha_analysis_runs.py tests/test_runtime_schema_bootstrap.py
git commit -m "feat(alpha): persist holdings analysis runs"
```

**Success standard:** A completed or failed run round-trips all four JSON sections; nullable agent results remain null on failure; users cannot read each other's runs; Alembic has one continuous head from `000019` to `000020`, including upgrade and downgrade coverage.

## Task 7: Replace The Report Service With The Canonical Pipeline

**Files:**
- Modify: `src/alpha/report_service.py`
- Modify: `tests/test_alpha_portfolio_report_service.py`

- [ ] **Step 1: Replace old recommendation tests with failing pipeline tests**

```python
from src.alpha.analysis_agents import AnalysisAgentError
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


SNAPSHOT = AnalysisSnapshot(
    symbol="600703.SH",
    market="a",
    currency="CNY",
    as_of="2026-06-22",
    quantity=300,
    weighted_avg_cost=13.333333,
    close=16.0,
    market_value=4800.0,
    unrealized_pnl=800.0,
    unrealized_pnl_ratio=0.06,
    position_ratio=0.08,
    stop_loss_ratio=-0.08,
    take_profit_ratio=0.20,
    technical={
        "ma20": 15.7,
        "ma60": 14.8,
        "ma20_gap": 0.02,
        "volume_ratio_20": 1.2,
        "bar_count": 61,
        "reclaimed_ma20": True,
    },
    fundamentals={"status": "ok", "pe_ratio": 18.2},
    news={"status": "unavailable", "items": []},
    data_quality={"status": "partial", "missing": ["news"]},
)
BULLISH_RESEARCH = ResearchPlan(
    rating="OVERWEIGHT",
    thesis="上涨趋势保持",
    technical_view="回踩 MA20 后重新站稳",
    fundamental_view="估值数据有限",
    sentiment_view="新闻不可用",
    catalysts=["成交量确认"],
    risks=["新闻缺失"],
    confidence=0.66,
    data_gaps=["news"],
)
BUY_PROPOSAL = TraderProposal(
    action="BUY",
    reasoning="研究方向偏多且位置未追高",
    entry_low=15.8,
    entry_high=16.2,
    stop_loss=15.0,
    take_profit=19.0,
    position_ratio=0.1,
)


class FakeSnapshotBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def build(self, **kwargs):
        return self.snapshot


class FakeResearchManager:
    def __init__(self, research):
        self.research = research

    def analyze(self, snapshot):
        return self.research


class FailingResearchManager:
    def __init__(self, message):
        self.message = message

    def analyze(self, snapshot):
        raise AnalysisAgentError(self.message)


class FakeTrader:
    def __init__(self, proposal):
        self.proposal = proposal

    def propose(self, snapshot, research):
        return self.proposal


def _seed_analysis_holding(store):
    store.insert_alpha_holdings_entry(
        symbol="600703.SH",
        buy_date="2026-06-01",
        buy_price=13.333333,
        quantity=300,
    )


def test_report_runs_snapshot_research_trader_risk_and_persists(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_analysis_holding(store)
    service = AlphaPortfolioReportService(
        store=store,
        snapshot_builder=FakeSnapshotBuilder(SNAPSHOT),
        research_manager=FakeResearchManager(BULLISH_RESEARCH),
        trader=FakeTrader(BUY_PROPOSAL),
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    report = service.generate_report({"symbols": ["600703.SH"], "backtest_window": "60d"})

    item = report["items"][0]
    assert item["status"] == "completed"
    assert item["research"]["rating"] == "OVERWEIGHT"
    assert item["trader"]["action"] == "BUY"
    assert item["risk"]["action"] == "ADD"
    assert store.get_alpha_analysis_run(item["run_id"])["symbol"] == "600703.SH"


def test_report_persists_visible_failure_without_mock_decision(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_analysis_holding(store)
    service = AlphaPortfolioReportService(
        store=store,
        snapshot_builder=FakeSnapshotBuilder(SNAPSHOT),
        research_manager=FailingResearchManager("DeepSeek timeout"),
        trader=FakeTrader(BUY_PROPOSAL),
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    item = service.generate_report({"symbols": ["600703.SH"]})["items"][0]

    assert item["status"] == "failed"
    assert item["research"] is None
    assert item["trader"] is None
    assert item["risk"] is None
    assert "DeepSeek timeout" in item["error"]
```

- [ ] **Step 2: Verify orchestration tests fail against the old report**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_portfolio_report_service.py -q
```

Expected: new assertions fail because the old response has `shadow` and `recommendation` instead of `research`, `trader`, and `risk`.

- [ ] **Step 3: Rewrite `AlphaPortfolioReportService.generate_report`**

For each requested or stored holding symbol, initialize every stage to null and place snapshot construction inside the same audited error boundary:

```python
snapshot = None
research = None
trader = None
risk = None
try:
    snapshot = self._snapshot_builder.build(
        symbol=symbol,
        lots=lots_by_symbol[symbol],
        portfolio_market_value=market_totals[market],
    )
    research = self._research_manager.analyze(snapshot)
    trader = self._trader.propose(snapshot, research)
    risk = evaluate_risk(
        snapshot,
        research,
        trader,
        max_position_ratio=self._max_position_ratio,
    )
    status = "completed"
    error = None
except (ValueError, AnalysisAgentError) as exc:
    status = "failed"
    error = str(exc)

run_id = self._store.insert_alpha_analysis_run(
    symbol=symbol,
    status=status,
    snapshot=snapshot.model_dump() if snapshot else None,
    research=research.model_dump() if research else None,
    trader=trader.model_dump() if trader else None,
    risk=risk.model_dump() if risk else None,
    model_name=self._model_name,
    error=error,
)
```

Return `generated_at`, `backtest_window`, `analysis_input`, and `items`. Each item is the persisted run shape plus the existing backtest section. Remove `_build_shadow_section`, `_build_recommendation`, `ShadowOpinionProvider`, `_latest_workbench`, and all `shadow`/`recommendation` response fields. Keep symbol normalization and backtest calculation only where directly used.

- [ ] **Step 4: Run report, persistence, and backtest tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_portfolio_report_service.py tests/test_alpha_analysis_runs.py tests/test_backtest_engine.py tests/test_backtest_metrics.py -q
```

Expected: all tests pass and `rg -n "_build_shadow_section|_build_recommendation|ShadowOpinionProvider" src/alpha/report_service.py` returns no matches.

- [ ] **Step 5: Commit the canonical service**

```bash
git add src/alpha/report_service.py tests/test_alpha_portfolio_report_service.py
git commit -m "refactor(alpha): make DeepSeek pipeline canonical"
```

**Success standard:** Every report item follows exactly one path; completed items contain snapshot, Research, Trader, Risk, and run ID; failed items contain snapshot, error, and null decisions; old shadow and rule recommendation builders no longer exist.

## Task 8: Update API Contracts And Analysis History

**Files:**
- Modify: `src/api/routes_alpha.py`
- Modify: `tests/test_alpha_routes.py`

- [ ] **Step 1: Write failing endpoint tests**

```python
from src.api import routes_alpha


class FakeReportService:
    def generate_report(self, payload):
        return {
            "generated_at": "2026-06-22T15:10:00+08:00",
            "backtest_window": payload["backtest_window"],
            "analysis_input": {"symbols": payload["symbols"], "positions": payload["positions"]},
            "items": [
                {
                    "run_id": "alpha-analysis-test",
                    "status": "completed",
                    "snapshot": {"symbol": "600703.SH", "close": 16.0},
                    "research": {"rating": "OVERWEIGHT"},
                    "trader": {"action": "BUY"},
                    "risk": {"action": "ADD"},
                    "model_name": "deepseek-v4-pro",
                    "error": None,
                }
            ],
        }


def test_report_endpoint_removes_shadow_and_returns_final_risk(authenticated_client, monkeypatch):
    monkeypatch.setattr(routes_alpha, "_build_report_service", lambda store: FakeReportService())
    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report",
        json={"symbols": ["600703"], "backtest_window": "60d"},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "shadow" not in item
    assert "recommendation" not in item
    assert item["risk"]["action"] in {"ADD", "HOLD", "REDUCE", "EXIT"}


def test_analysis_history_is_user_scoped(authenticated_client, pg_store):
    response = authenticated_client.get(
        "/api/v1/alpha/analysis-runs",
        params={"symbol": "600703.SH", "limit": 10},
    )
    assert response.status_code == 200
    assert "items" in response.json()
```

- [ ] **Step 2: Verify route tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py -q
```

Expected: fails because the old report still accepts `include_shadow` and the history route does not exist.

- [ ] **Step 3: Wire production dependencies and remove the old request field**

Construct `LLMClient(Settings())`, `AnalysisSnapshotBuilder` with production A-share/US loaders, `ResearchManager`, and `Trader` in `_build_report_service(store)`. The report request accepts only:

```json
{
  "symbols": ["600703.SH"],
  "positions": [],
  "include_backtest": true,
  "backtest_window": "60d",
  "opening_cash": 10000
}
```

Add:

```python
@router.get("/analysis-runs")
def list_analysis_runs(
    symbol: str | None = None,
    limit: int = 20,
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    normalized = normalize_report_symbol(symbol) if symbol else None
    safe_limit = min(max(limit, 1), 100)
    return {"items": store.list_alpha_analysis_runs(symbol=normalized, limit=safe_limit)}
```

- [ ] **Step 4: Run API and authentication tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py tests/test_route_authentication.py tests/test_user_isolation.py -q
```

Expected: report and history routes require authentication, normalize symbols, cap history at 100, and expose no cross-user records.

- [ ] **Step 5: Commit API changes**

```bash
git add src/api/routes_alpha.py tests/test_alpha_routes.py
git commit -m "feat(alpha): expose structured holdings decisions"
```

**Success standard:** The canonical report request has no shadow flag; a successful response includes final risk action and audit ID; a failed DeepSeek call remains HTTP 200 at report level with an item-level failed status; history is authenticated, normalized, bounded, and tenant-isolated.

## Task 9: Replace The Dashboard Recommendation UI

**Files:**
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/styles/alpha.css`
- Modify: `tests/test_dashboard_alpha_tab.py`
- Modify: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: Write failing dashboard contract tests**

```python
def test_dashboard_contains_structured_decision_sections(_patch_auth):
    html = _dashboard_html()
    for marker in [
        "alpha-analysis-status",
        "alpha-research-section",
        "alpha-trader-section",
        "alpha-risk-section",
        "alpha-data-quality",
        "alpha-analysis-history",
    ]:
        assert marker in html


def test_dashboard_removes_shadow_decision_path(_patch_auth):
    html = _dashboard_html()
    for marker in [
        "alpha-report-include-shadow",
        "包含影子持仓",
        "模拟建议",
        "item.shadow",
        "item.recommendation",
    ]:
        assert marker not in html
```

- [ ] **Step 2: Verify dashboard tests fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: fails because the old shadow controls and rendering remain.

- [ ] **Step 3: Update HTML controls and response payload**

Remove the `alpha-report-include-shadow` checkbox. Add an analysis status strip and history container. Define `const ALPHA_ANALYSIS_RUNS_API = '/api/v1/alpha/analysis-runs';`. `loadAlphaReport()` must omit `include_shadow`, send only the canonical Task 8 request fields, and call `loadAlphaAnalysisHistory(symbol)` after a completed or failed response so the audit list refreshes immediately.

- [ ] **Step 4: Render one final decision with expandable evidence**

For completed items, render:

```javascript
const snapshot = item.snapshot || {};
const research = item.research || {};
const trader = item.trader || {};
const risk = item.risk || {};
const action = String(risk.action || '').toUpperCase();
const actionClass = ['ADD', 'HOLD', 'REDUCE', 'EXIT'].includes(action)
  ? action.toLowerCase()
  : 'failed';
```

The visible card must include symbol, close date, close, weighted cost, quantity, market value, unrealized P&L amount and ratio, final action, risk reason, approved position ratio, entry range, stop loss, take profit, Research rating/confidence, `data_quality.missing`, model name, and run ID. Use `<details>` for Research, Trader, and triggered risk rules.

For failed items, render only deterministic snapshot values plus:

```javascript
`<div class="alpha-analysis-error">DeepSeek 分析失败：${escapeHtml(item.error || '未知错误')}</div>`
```

Do not infer `HOLD` in JavaScript.

- [ ] **Step 5: Add scoped styles**

Add styles under `.alpha-report-item` for `.add`, `.hold`, `.reduce`, `.exit`, `.alpha-analysis-error`, `.alpha-data-quality`, and evidence `<details>`. Keep existing dashboard color tokens and do not modify `dashboard.css` or other views.

- [ ] **Step 6: Run dashboard tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: all tests pass and the forbidden shadow markers are absent from rendered dashboard HTML.

- [ ] **Step 7: Commit the dashboard replacement**

```bash
git add src/api/dashboard_page/partials/view_alpha.html src/api/dashboard_page/scripts/alpha.js src/api/dashboard_page/styles/alpha.css tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py
git commit -m "feat(alpha): show auditable holdings decisions"
```

**Success standard:** The page shows one final action, close-based P&L, exact data timestamp, and expandable Research/Trader/Risk evidence; DeepSeek errors are visible and never displayed as a recommendation; no shadow control or old recommendation renderer remains.

## Task 10: Full Verification, Documentation, Migration, And Deployment Gate

**Files:**
- Modify: `README.md`
- Verify: all files changed in Tasks 1-9

- [ ] **Step 1: Document the operational contract**

Add a `Holdings analysis` section to `README.md` containing:

```text
Facts and P&L -> Research Manager (DeepSeek) -> Trader (DeepSeek) -> deterministic Risk Check

The page is decision support only and never submits an order. News is currently reported as unavailable.
DeepSeek failures are shown as failed analyses; the application does not substitute mock advice.
Required environment: LLM_PROVIDER=deepseek, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL.
```

- [ ] **Step 2: Run focused feature tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_models.py tests/test_alpha_analysis_snapshot.py tests/test_alpha_analysis_agents.py tests/test_alpha_analysis_risk.py tests/test_alpha_analysis_runs.py tests/test_alpha_portfolio_report_service.py tests/test_alpha_routes.py tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py tests/test_llm_client.py -q
```

Expected: all focused tests pass.

- [ ] **Step 3: Run the full regression suite**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q
```

Expected: no new failures relative to the repository baseline.

- [ ] **Step 4: Run static checks and legacy-path scans**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/alpha src/agents/llm_client.py src/api/routes_alpha.py tests/test_alpha_analysis_models.py tests/test_alpha_analysis_snapshot.py tests/test_alpha_analysis_agents.py tests/test_alpha_analysis_risk.py tests/test_alpha_analysis_runs.py
rg -n "include_shadow|alpha-report-include-shadow|_build_shadow_section|_build_recommendation|item\.shadow|item\.recommendation" src/alpha src/api/routes_alpha.py src/api/dashboard_page
```

Expected: Ruff exits 0; `rg` exits 1 with no matches.

- [ ] **Step 5: Verify migration continuity in the deployment environment**

Run on the server after pulling the commit:

```bash
/home/ec2-user/miniconda3/envs/py311/bin/python -m alembic current
/home/ec2-user/miniconda3/envs/py311/bin/python -m alembic heads
/home/ec2-user/miniconda3/envs/py311/bin/python -m alembic upgrade head
/home/ec2-user/miniconda3/envs/py311/bin/python -m alembic current
```

Expected: the first two commands show a continuous path ending at `20260622_000020`; after upgrade, `current` reports `20260622_000020 (head)`.

- [ ] **Step 6: Perform browser acceptance with one A-share and one US holding**

Acceptance sequence:

1. Save two lots for one A-share symbol and verify weighted cost.
2. Generate analysis and verify close date, P&L amount, P&L ratio, Research rating, Trader proposal, final risk action, model name, and run ID.
3. Switch to US holdings and repeat with USD labels.
4. Temporarily use an invalid DeepSeek key, generate again, and verify the card says `DeepSeek 分析失败` with no final action.
5. Restore the key and verify `GET /api/v1/alpha/analysis-runs?symbol=<symbol>` includes both the completed and failed run.

- [ ] **Step 7: Commit documentation after verification**

```bash
git add README.md
git commit -m "docs(alpha): document holdings decision pipeline"
```

**Success standard:** Focused and full tests pass, Ruff passes, no old shadow/recommendation markers remain, Alembic reports exactly one head at `000020`, both markets render correct currency and close-based P&L, completed and failed DeepSeek runs are independently auditable, and the feature never submits an order.

## Final Acceptance Matrix

| Requirement | Owning task | Pass condition |
|---|---:|---|
| Weighted cost and close P&L are deterministic | 3 | Fixture arithmetic equals snapshot values exactly |
| Research Manager uses only supplied evidence | 4 | Prompt contract and `data_gaps` tests pass |
| Trader consumes Research rather than re-researching | 4 | Second prompt contains validated Research JSON |
| DeepSeek assists decisions without controlling hard risk | 2, 5 | LLM failures are explicit; stop loss overrides BUY |
| One user-facing action vocabulary | 5, 7, 9 | Only Risk emits `ADD/HOLD/REDUCE/EXIT` |
| No legacy shadow recommendation path | 7, 8, 9, 10 | Repository scan returns no forbidden markers |
| Full audit history | 6, 7, 8 | Completed and failed runs round-trip by run ID |
| User isolation | 6, 8 | Cross-user store and endpoint tests return no records |
| A-share and US support | 3, 9 | Currency, providers, close dates, and rendering pass for both |
| No silent mock advice | 2, 7, 9 | Missing/invalid DeepSeek produces failed status and null decision |
| No automatic execution | 9, 10 | No order API is called and README states decision-support boundary |

## Self-Review Results

- Spec coverage: Research Manager, Trader, DeepSeek, trend-pullback rules, position-aware P&L, hard stop loss/take profit, audit history, A-share/US behavior, visible failures, and UI replacement each map to at least one task.
- Placeholder scan: the plan contains no deferred implementation markers or unspecified error-handling steps.
- Type consistency: `ResearchPlan`, `TraderProposal`, `RiskDecision`, and `AnalysisRunResult` names and fields are consistent from schema definition through persistence, API, and UI tasks.
- Legacy convergence: old `include_shadow`, `shadow`, and `recommendation` paths are removed in the same rollout; there is one canonical report endpoint and one final decision source.
