# Holdings Analysis Streaming Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synchronous multi-symbol holdings report with a single-symbol, per-stage streaming pipeline that emits SSE events and stores auditable run history.

**Architecture:** Frontend posts one symbol to `POST /api/v1/alpha/analysis-runs` and receives an HTTP 202 with a `run_id` and `stream_url`. Backend runs snapshot/research/trader/risk/backtest stages, persisting events to `alpha_analysis_run_events` after each stage, and pushes SSE to the client. Dashboard replaces the multi-symbol report card with a fixed-height Analysis Center plus a right-side drawer for full detail.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Starlette `EventSourceResponse`, vanilla JS (SSE), Alembic, pytest.

---

## Scope And Locked Decisions

- Analysis subject is a single symbol the user has previously saved in `alpha_holdings_entries`. Watchlist symbols are not eligible.
- One user, one active run. Repeating the same symbol returns the existing run; clicking another symbol while one is running surfaces a 409 with the active run id.
- Each run fetches market evidence exactly once and reuses it across snapshot, research, trader, risk, and backtest.
- Stages are: `accepted → snapshot → research → trader → risk → backtest → completed | failed`. DeepSeek is never called more than once per stage.
- DeepSeek failure on any stage marks the run `failed`, preserves already-completed stages, and never produces a mock HOLD.
- The synchronous `POST /api/v1/alpha/portfolio/report` endpoint is removed in the same rollout.
- Cost/quantity come from `alpha_holdings_entries`; the request payload cannot override them.

## File Responsibility Map

### Create
- `src/alpha/analysis_run_models.py` — Pydantic contracts for run creation, stage updates, run summary, run detail, event payloads.
- `src/alpha/analysis_run_service.py` — `AlphaAnalysisRunService` orchestrating the 5-stage execution and event emission.
- `src/alpha/analysis_event_broadcaster.py` — In-process pub/sub for SSE fan-out per `run_id`.
- `src/alpha/analysis_run_store.py` — `AnalysisRunStore` wrapping DB operations: create/update run, append events, fetch detail, list with cursor.
- `alembic/versions/20260622_000021_add_analysis_run_events.py` — Adds `alpha_analysis_run_events` table and extends `alpha_analysis_runs` with `current_stage`, `started_at`, `finished_at`, `updated_at`.
- `tests/test_alpha_analysis_run_models.py` — Schema boundary tests.
- `tests/test_alpha_analysis_run_service.py` — Stage orchestration, single-active-run, market data reused, failure preservation.
- `tests/test_alpha_analysis_run_events.py` — Event store, sequence monotonicity, user isolation, Last-Event-ID resume.
- `tests/test_alpha_analysis_routes_v2.py` — POST returns 202, GET detail, GET events, list with cursor.

### Modify
- `src/storage/models.py` — Extend `AlphaAnalysisRunRow`, add `AlphaAnalysisRunEventRow`.
- `src/storage/runtime_store.py` — Replace `insert_alpha_analysis_run` with extended schema; add event methods.
- `src/api/routes_alpha.py` — Remove `POST /portfolio/report`; add `POST /analysis-runs`, `GET /analysis-runs`, `GET /analysis-runs/{run_id}`, `GET /analysis-runs/{run_id}/events`.
- `src/api/dashboard_page/partials/view_alpha.html` — Remove top-level "生成报告" / "保存并生成报告"; add per-holding "分析" button, full-width Analysis Center, right drawer.
- `src/api/dashboard_page/scripts/alpha.js` — Replace `loadAlphaReport` with `startAlphaAnalysis(symbol)`, `openAlphaAnalysisDrawer(runId)`, SSE subscriber, list pagination.
- `src/api/dashboard_page/styles/alpha.css` — Fixed-height analysis list, drawer styles, status filters.
- `tests/test_alpha_routes.py` — Remove `portfolio/report` tests; ensure 404.
- `tests/test_alpha_portfolio_report_service.py` — Mark as deprecated or delete; ensure no other module imports it.
- `tests/test_runtime_schema_bootstrap.py` — Update bootstrap to load new columns.
- `README.md` — Document the streaming pipeline, single-symbol invariant, and SSE contract.

## Task 1: Persist Stage Events And Run Lifecycle

**Files:**
- Create: `alembic/versions/20260622_000021_add_analysis_run_events.py`
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Modify: `tests/test_runtime_schema_bootstrap.py`

- [ ] **Step 1: Write failing migration / model test**

```python
# tests/test_alpha_analysis_run_events.py
def test_runs_and_events_persist_with_monotonic_seq(pg_engine):
    from src.core.tenant import TenantContext
    from src.storage.runtime_store import RuntimeStore
    from src.alpha.analysis_run_store import AnalysisRunStore

    store = AnalysisRunStore(pg_engine, TenantContext("alice"))

    run_id = store.create_run(symbol="MU.US", model_name="deepseek-v4-pro")
    assert run_id.startswith("alpha-ar-")

    event_ids: list[int] = []
    for stage in ["accepted", "snapshot", "research"]:
        event_ids.append(
            store.append_event(run_id=run_id, stage=stage, status="done", payload={"stage": stage})
        )

    assert event_ids == sorted(event_ids)
    events = store.list_events(run_id)
    assert [e["stage"] for e in events] == ["accepted", "snapshot", "research"]
    assert all(e["user_id"] == "alice" for e in events)
```

- [ ] **Step 2: Run test to confirm failure**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_events.py -q
```

Expected: ImportError / AttributeError because `AnalysisRunStore` does not exist.

- [ ] **Step 3: Add migration `20260622_000021_add_analysis_run_events.py`**

Revision: `20260622_000021`, down_revision: `20260622_000020`.

```python
op.add_column("alpha_analysis_runs", sa.Column("current_stage", sa.String(length=32), nullable=False, server_default="accepted"))
op.add_column("alpha_analysis_runs", sa.Column("started_at", sa.DateTime(), nullable=True))
op.add_column("alpha_analysis_runs", sa.Column("finished_at", sa.DateTime(), nullable=True))
op.add_column("alpha_analysis_runs", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))

op.create_table(
    "alpha_analysis_run_events",
    sa.Column("event_id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("run_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("seq", sa.Integer, nullable=False),
    sa.Column("event_type", sa.String(length=32), nullable=False),
    sa.Column("stage", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("run_id", "seq", name="uq_alpha_run_events_run_seq"),
)
```

`downgrade()` drops the table and the new columns.

- [ ] **Step 4: Extend `AlphaAnalysisRunRow` and add `AlphaAnalysisRunEventRow`**

```python
class AlphaAnalysisRunRow(Base):
    __tablename__ = "alpha_analysis_runs"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    trader_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    backtest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AlphaAnalysisRunEventRow(Base):
    __tablename__ = "alpha_analysis_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_alpha_run_events_run_seq"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 5: Implement `AnalysisRunStore` with `create_run`, `update_run`, `append_event`, `list_events`, `get_run`, `list_runs`**

`create_run(symbol, model_name)` returns a run id prefixed with `alpha-ar-` and inserts a row with status `accepted`, current_stage `accepted`, started_at `now()`.

`update_run(run_id, status=None, current_stage=None, snapshot=None, research=None, trader=None, risk=None, backtest=None, error=None, error_stage=None, finished_at=None)` updates only provided fields, sets updated_at.

`append_event(run_id, stage, status, payload=None)` is user-scoped. Computes `seq` as `max(seq)+1` for that run under the same tenant; returns the new seq.

`list_events(run_id, after_seq=None)` returns events with `seq > after_seq` ordered by seq.

`get_run(run_id)` returns summary dict including count of events.

`list_runs(market=None, status_filter=None, limit=20, cursor_run_id=None)` returns cursor-paginated summaries (symbol, current_stage, status, risk_action, research_rating, research_confidence, close_date, created_at). Cursor is `created_at,run_id` composite.

- [ ] **Step 6: Run migration and store tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m alembic heads
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_events.py tests/test_runtime_schema_bootstrap.py -q
```

Expected: alembic head is `20260622_000021`; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/20260622_000021_add_analysis_run_events.py src/storage/models.py src/storage/runtime_store.py src/alpha/analysis_run_store.py tests/test_alpha_analysis_run_events.py tests/test_runtime_schema_bootstrap.py
git commit -m "feat(alpha): persist analysis run lifecycle and events"
```

**Success standard:** Run row is created with `current_stage="accepted"`; each appended event has a strictly increasing `seq`; users cannot read other users' runs or events; alembic head is `20260622_000021`.

## Task 2: Pydantic Contracts For Streaming Pipeline

**Files:**
- Create: `src/alpha/analysis_run_models.py`
- Create: `tests/test_alpha_analysis_run_models.py`

- [ ] **Step 1: Write failing schema tests**

```python
import pytest
from pydantic import ValidationError

from src.alpha.analysis_run_models import (
    AnalysisRunCreateRequest,
    AnalysisRunCreatedResponse,
    AnalysisRunSummary,
    AnalysisRunDetail,
    AnalysisStageUpdate,
)


def test_create_request_rejects_empty_symbol():
    with pytest.raises(ValidationError):
        AnalysisRunCreateRequest(symbol="", backtest_window="60d", include_backtest=True)


def test_stage_update_cumulative_payload():
    payload = AnalysisStageUpdate(
        run_id="alpha-ar-1",
        symbol="MU.US",
        stage="research",
        status="done",
        message="研究结论已生成",
        snapshot={"close": 16.0},
        research={"rating": "OVERWEIGHT"},
        trader=None,
        risk=None,
        backtest=None,
    )
    assert payload.stage == "research"
    assert payload.snapshot["close"] == 16.0


def test_summary_keys_are_stable():
    summary = AnalysisRunSummary(
        run_id="alpha-ar-1",
        symbol="MU.US",
        market="us",
        status="completed",
        current_stage="completed",
        risk_action="ADD",
        research_rating="OVERWEIGHT",
        research_confidence=0.7,
        close_date="2026-06-22",
        created_at="2026-06-22T15:10:00+08:00",
    )
    assert summary.market == "us"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_models.py -q
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement Pydantic models**

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field


MarketTag = Literal["a", "us"]
RunStatus = Literal["accepted", "running", "completed", "failed"]
StageName = Literal["accepted", "snapshot", "research", "trader", "risk", "backtest", "completed", "failed"]
StageStatus = Literal["started", "done", "failed"]


class AnalysisRunCreateRequest(BaseModel):
    symbol: str = Field(min_length=1)
    backtest_window: str = Field(default="60d")
    include_backtest: bool = Field(default=True)


class AnalysisRunCreatedResponse(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    stream_url: str
    created_at: str


class AnalysisStageUpdate(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    stage: StageName
    status: StageStatus
    message: str = ""
    snapshot: Optional[dict] = None
    research: Optional[dict] = None
    trader: Optional[dict] = None
    risk: Optional[dict] = None
    backtest: Optional[dict] = None
    error: Optional[str] = None
    error_stage: Optional[StageName] = None
    seq: int


class AnalysisRunSummary(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    current_stage: StageName
    risk_action: Optional[str] = None
    research_rating: Optional[str] = None
    research_confidence: Optional[float] = None
    close_date: Optional[str] = None
    created_at: str
    finished_at: Optional[str] = None


class AnalysisRunDetail(BaseModel):
    run_id: str
    symbol: str
    market: MarketTag
    status: RunStatus
    current_stage: StageName
    model_name: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    snapshot: Optional[dict] = None
    research: Optional[dict] = None
    trader: Optional[dict] = None
    risk: Optional[dict] = None
    backtest: Optional[dict] = None
    error: Optional[str] = None
    error_stage: Optional[StageName] = None
```

- [ ] **Step 4: Run tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_models.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/alpha/analysis_run_models.py tests/test_alpha_analysis_run_models.py
git commit -m "feat(alpha): define streaming analysis contracts"
```

**Success standard:** All five Pydantic models validate, reject empty symbol, and serialize to stable JSON. The stage update payload always carries the cumulative snapshot/research/trader/risk/backtest snapshot.

## Task 3: Single-Active-Run Lock And Service Orchestrator

**Files:**
- Create: `src/alpha/analysis_event_broadcaster.py`
- Create: `src/alpha/analysis_run_service.py`
- Create: `tests/test_alpha_analysis_run_service.py`

- [ ] **Step 1: Write failing service tests**

```python
import asyncio
import pytest

from src.alpha.analysis_event_broadcaster import EventBroadcaster
from src.alpha.analysis_run_service import AlphaAnalysisRunService
from src.alpha.analysis_run_models import AnalysisRunCreateRequest


class FakeStore:
    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.events: dict[str, list[dict]] = {}
        self.active: set[str] = set()

    def has_active_run(self, user_id: str, symbol: str) -> dict | None:
        for run in self.runs.values():
            if run["user_id"] == user_id and run["status"] in {"accepted", "running"}:
                return run
        return None

    def get_active_for_user(self, user_id: str) -> dict | None:
        for run in self.runs.values():
            if run["user_id"] == user_id and run["status"] in {"accepted", "running"}:
                return run
        return None

    def create_run(self, *, symbol: str, model_name: str, user_id: str) -> str:
        run_id = f"alpha-ar-{len(self.runs) + 1}"
        self.runs[run_id] = {
            "run_id": run_id,
            "user_id": user_id,
            "symbol": symbol,
            "status": "accepted",
            "current_stage": "accepted",
            "model_name": model_name,
        }
        self.events[run_id] = []
        return run_id

    def update_run(self, run_id: str, **fields) -> None:
        self.runs[run_id].update(fields)

    def append_event(self, *, run_id: str, stage: str, status: str, payload: dict) -> int:
        seq = len(self.events[run_id]) + 1
        self.events[run_id].append({"seq": seq, "stage": stage, "status": status, "payload": payload})
        return seq

    def get_run(self, run_id: str) -> dict | None:
        return self.runs.get(run_id)


class FakeLLM:
    def generate_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 1000):
        if "ResearchPlan" in system_prompt or "持仓研究经理" in system_prompt:
            return {
                "rating": "OVERWEIGHT",
                "thesis": "t",
                "technical_view": "tv",
                "fundamental_view": "fv",
                "sentiment_view": "sv",
                "catalysts": [],
                "risks": [],
                "confidence": 0.6,
                "data_gaps": ["news"],
            }
        return {
            "action": "BUY",
            "reasoning": "r",
            "entry_low": 10.0,
            "entry_high": 11.0,
            "stop_loss": 9.0,
            "take_profit": 12.0,
            "position_ratio": 0.1,
        }


class FakeSnapshotBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def build(self, *, symbol: str, lots, portfolio_market_value: float):
        from src.alpha.analysis_models import AnalysisSnapshot
        self.calls += 1
        return self.snapshot


def _make_snapshot():
    from src.alpha.analysis_models import AnalysisSnapshot
    return AnalysisSnapshot(
        symbol="MU.US", market="us", currency="USD", as_of="2026-06-22",
        quantity=10, weighted_avg_cost=100.0, close=110.0, market_value=1100.0,
        unrealized_pnl=100.0, unrealized_pnl_ratio=0.1, position_ratio=0.05,
        stop_loss_ratio=-0.08, take_profit_ratio=0.20,
        technical={"ma20": 108.0, "ma60": 100.0, "reclaimed_ma20": True, "ma20_gap": 0.01, "volume_ratio_20": 1.1, "bar_count": 61},
        fundamentals={"status": "ok"}, news={"status": "unavailable", "items": []},
        data_quality={"status": "partial", "missing": ["news"]},
    )


def test_start_returns_202_payload_and_runs_stages(monkeypatch):
    from src.alpha.analysis_run_service import AlphaAnalysisRunService
    from src.alpha.analysis_agents import ResearchManager, Trader
    store = FakeStore()
    service = AlphaAnalysisRunService(
        store=store,
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=ResearchManager(FakeLLM()),
        trader=Trader(FakeLLM()),
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )

    response = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))

    assert response["status"] == "accepted"
    assert response["stream_url"].endswith(f"/{response['run_id']}/events")

    asyncio.run(service.execute(response["run_id"]))

    run = store.get_run(response["run_id"])
    assert run["status"] == "completed"
    assert run["current_stage"] == "completed"
    assert run["risk"]["action"] == "ADD"


def test_repeat_request_for_same_symbol_returns_existing_run():
    from src.alpha.analysis_run_service import AlphaAnalysisRunService
    store = FakeStore()
    service = AlphaAnalysisRunService(
        store=store,
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=None, trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice", model_name="deepseek-v4-pro", max_position_ratio=0.2,
    )
    first = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    second = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    assert first["run_id"] == second["run_id"]


def test_other_symbol_while_active_returns_conflict():
    from src.alpha.analysis_run_service import AlphaAnalysisRunService
    store = FakeStore()
    service = AlphaAnalysisRunService(
        store=store,
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}, {"symbol": "MSFT.US", "buy_price": 200.0, "quantity": 5, "buy_date": "2026-01-01"}]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=None, trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice", model_name="deepseek-v4-pro", max_position_ratio=0.2,
    )
    first = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    with pytest.raises(AlphaAnalysisConflict) as exc:
        service.start(AnalysisRunCreateRequest(symbol="MSFT.US", backtest_window="60d", include_backtest=True))
    assert exc.value.active_run_id == first["run_id"]


class FakeHoldingsStore:
    def __init__(self, entries):
        self.entries = [dict(e, entry_id=f"e{i}") for i, e in enumerate(entries)]

    def list_alpha_holdings_entries(self):
        return self.entries
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_service.py -q
```

Expected: ImportError on `AlphaAnalysisRunService`, `EventBroadcaster`, `AlphaAnalysisConflict`.

- [ ] **Step 3: Implement `EventBroadcaster`**

```python
import asyncio
from collections import defaultdict


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, run_id: str, event: dict) -> None:
        for queue in list(self._subscribers.get(run_id, ())):
            queue.put_nowait(event)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[run_id].discard(queue)
```

- [ ] **Step 4: Implement `AlphaAnalysisRunService`**

Constructor stores injected `store`, `holdings_store`, `snapshot_builder`, `research_manager`, `trader`, `broadcaster`, `user_id`, `model_name`, `max_position_ratio`.

`start(request)`:
1. Look up holdings for `request.symbol` from `holdings_store.list_alpha_holdings_entries()` filtered by symbol. If empty, raise `AlphaAnalysisNotFound`.
2. If existing active run for user, return its `stream_url` (same symbol) or raise `AlphaAnalysisConflict` (different symbol).
3. Create run, append `accepted` event, return `AnalysisRunCreatedResponse`.

`execute(run_id)`:
1. `snapshot`: build once, store snapshot_json, emit stage update.
2. `research`: call manager, store research_json, emit.
3. `trader`: call trader, store trader_json, emit.
4. `risk`: `evaluate_risk(snapshot, research, trader, max_position_ratio)`, store risk_json, emit.
5. `backtest`: compute using stored bars from snapshot (not new fetch), store backtest_json, emit.
6. `completed`: status=completed, current_stage=completed, finished_at=now.

Failure: catch in any stage → set `status=failed`, `error_stage=stage`, `error=str(exc)`, finished_at=now, emit `failed` event. Do not produce mock HOLD.

`broadcast_stage_update(stage, status, ...)`:
1. Build `AnalysisStageUpdate` payload.
2. Persist event with `append_event`.
3. `broadcaster.publish(run_id, payload.model_dump())`.

- [ ] **Step 5: Run tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_service.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/alpha/analysis_event_broadcaster.py src/alpha/analysis_run_service.py tests/test_alpha_analysis_run_service.py
git commit -m "feat(alpha): add single-active-run service and event broadcaster"
```

**Success standard:** Starting the same symbol returns the same run id; starting a different symbol while one is active raises `AlphaAnalysisConflict`; market data is fetched exactly once per run; failed stages preserve earlier stage JSON and never produce a mock HOLD.

## Task 4: SSE Endpoint, Detail Endpoint, And List Endpoint

**Files:**
- Modify: `src/api/routes_alpha.py`
- Modify: `tests/test_alpha_routes.py`
- Create: `tests/test_alpha_analysis_routes_v2.py`

- [ ] **Step 1: Write failing route tests**

```python
# tests/test_alpha_analysis_routes_v2.py
def test_post_returns_202_with_run_id_and_stream_url(authenticated_client, monkeypatch):
    from src.api import routes_alpha
    monkeypatch.setattr(
        routes_alpha,
        "_build_run_service",
        lambda store, user_id: FakeRunService(),
    )
    response = authenticated_client.post(
        "/api/v1/alpha/analysis-runs",
        json={"symbol": "MU.US", "backtest_window": "60d", "include_backtest": True},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["symbol"] == "MU.US"
    assert body["stream_url"].endswith("/events")


def test_old_portfolio_report_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report", json={"symbols": ["MU.US"]}
    )
    assert response.status_code == 404


def test_list_runs_is_cursor_paginated_and_summary_only(authenticated_client, pg_store):
    response = authenticated_client.get(
        "/api/v1/alpha/analysis-runs?market=us&limit=20"
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "next_cursor" in body
    if body["items"]:
        first = body["items"][0]
        assert {"run_id", "symbol", "status", "current_stage", "risk_action", "research_rating", "created_at"} <= set(first.keys())
        assert "snapshot" not in first
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_routes_v2.py tests/test_alpha_routes.py -q
```

Expected: New endpoint tests fail; old `portfolio/report` tests must be removed.

- [ ] **Step 3: Replace `routes_alpha.py` portfolio section with new endpoints**

Remove `POST /portfolio/report`, `_build_report_service`, `_latest_close_price_map`, `_rebuild_holdings_portfolio`. Add:

```python
@router.post("/analysis-runs", status_code=202)
def start_analysis_run(
    payload: dict,
    tenant: TenantContext = Depends(get_tenant_context),
    store: RuntimeStore = Depends(get_user_runtime_store),
    background: BackgroundTasks = None,
) -> dict:
    request = AnalysisRunCreateRequest(**payload)
    service = _build_run_service(store, tenant.user_id)
    response = service.start(request)
    if background is not None:
        background.add_task(service.execute, response["run_id"])
    return response


@router.get("/analysis-runs")
def list_analysis_runs(
    market: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    safe_limit = min(max(limit, 1), 100)
    run_store = AnalysisRunStore(store._engine, tenant)
    result = run_store.list_runs(market=market, status_filter=status_filter, limit=safe_limit, cursor_run_id=cursor)
    return result


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(
    run_id: str,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    run_store = AnalysisRunStore(store._engine, tenant)
    detail = run_store.get_run_detail(run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return detail


@router.get("/analysis-runs/{run_id}/events")
def stream_analysis_run_events(
    run_id: str,
    request: Request,
    store: RuntimeStore = Depends(get_user_runtime_store),
    tenant: TenantContext = Depends(get_tenant_context),
):
    run_store = AnalysisRunStore(store._engine, tenant)
    if not run_store.get_run(run_id):
        raise HTTPException(status_code=404, detail="analysis run not found")
    after_seq = int(request.headers.get("Last-Event-ID", 0))
    queue = broadcaster.subscribe(run_id)
    return EventSourceResponse(_event_iter(run_id, queue, run_store, after_seq=after_seq))
```

`_event_iter` yields existing events with `seq > after_seq`, then blocks on the broadcaster queue, terminating when the run reaches `completed`/`failed`.

- [ ] **Step 4: Update existing route tests to remove portfolio/report references**

`tests/test_alpha_routes.py`: remove all tests that hit `/portfolio/report`. Add a 404 assertion.

- [ ] **Step 5: Run tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_routes_v2.py tests/test_alpha_routes.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes_alpha.py tests/test_alpha_analysis_routes_v2.py tests/test_alpha_routes.py
git commit -m "feat(alpha): replace report endpoint with streaming analysis-runs API"
```

**Success standard:** POST returns 202 within ~50ms with run_id and stream_url; old `/portfolio/report` returns 404; list returns only summary fields, no full snapshot JSON; SSE delivers events in order and closes after the terminal event.

## Task 5: Single-Holding Card With Analysis Button

**Files:**
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/styles/alpha.css`
- Modify: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: Write failing dashboard contract tests**

```python
def test_dashboard_has_analysis_center_and_drawer(_patch_auth):
    html = _dashboard_html()
    for marker in [
        "alpha-analysis-center",
        "alpha-analysis-drawer",
        "alpha-holding-analyze",
    ]:
        assert marker in html


def test_dashboard_removes_legacy_report_markers(_patch_auth):
    html = _dashboard_html()
    for marker in [
        "alpha-report-generate",
        "alpha-report-include-shadow",
        "loadAlphaReport",
        "alphaPortfolioSymbols",
    ]:
        assert marker not in html
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: missing markers cause failures.

- [ ] **Step 3: Update `view_alpha.html`**

- Remove the "生成报告" button and "包含影子持仓" controls.
- Add `data-alpha-holding-analyze` button on each holding card.
- Add `<section id="alpha-analysis-center">` with status filters, a `alpha-analysis-list` container, and a `alpha-analysis-drawer` template.
- Keep top area market switcher, holding entry, current holdings.

- [ ] **Step 4: Update `alpha.js`**

- Remove `alphaPortfolioSymbols`, `loadAlphaReport`, `collectAlphaReportPositions`.
- Add `startAlphaAnalysis(symbol)`: posts to `/api/v1/alpha/analysis-runs`, inserts an active row, opens EventSource, updates row on each event.
- Add `openAlphaAnalysisDrawer(runId)`: fetches detail, renders drawer.
- Add `loadAlphaAnalysisList(cursor=null)`: paginated list.
- Add `escape`, `trapFocus`, drawer close handlers (Esc, overlay click, button).

- [ ] **Step 5: Update `alpha.css`**

- `.alpha-analysis-center { height: clamp(420px, 58vh, 620px); overflow: hidden; display: flex; flex-direction: column; }`
- `.alpha-analysis-list { flex: 1; overflow-y: auto; }`
- `.alpha-analysis-drawer { position: fixed; right: 0; top: 0; height: 100vh; width: min(720px, 92vw); }`
- Status filter row, status badges, active row highlight.

- [ ] **Step 6: Run dashboard tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/api/dashboard_page/partials/view_alpha.html src/api/dashboard_page/scripts/alpha.js src/api/dashboard_page/styles/alpha.css tests/test_dashboard_alpha_tab.py tests/test_dashboard_page_contract.py
git commit -m "feat(alpha): single-holding analysis center with SSE drawer"
```

**Success standard:** Page height is constant regardless of run count; 600px viewport is usable; opening MU run only shows MU details; Esc closes drawer and restores focus; active run row shows live stage.

## Task 6: Cleanup Old Endpoints And Documentation

**Files:**
- Delete: `src/alpha/report_service.py`
- Delete: `tests/test_alpha_portfolio_report_service.py`
- Modify: `README.md`

- [ ] **Step 1: Verify nothing imports the old report service**

```bash
rg -n "AlphaPortfolioReportService|portfolio/report|alpha_portfolio_report_service" src tests
```

Expected: zero matches.

- [ ] **Step 2: Remove old files and rerun tests**

```bash
git rm src/alpha/report_service.py tests/test_alpha_portfolio_report_service.py
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q
```

Expected: no import errors; full suite green.

- [ ] **Step 3: Document streaming pipeline in README.md**

Add a `Holdings Analysis Streaming` section under the existing `Holdings Analysis` block:

```text
单标的异步流式分析：
- POST /api/v1/alpha/analysis-runs 返回 202 + run_id + stream_url
- 阶段：accepted → snapshot → research → trader → risk → backtest → completed/failed
- 事件通过 SSE 推送，前端 EventSource 订阅
- 断线可通过 Last-Event-ID 续传
- 同一用户同时只允许一个活跃分析
- 数据源一次加载，5 阶段共用
- 旧 POST /api/v1/alpha/portfolio/report 已删除
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs(alpha): document streaming analysis pipeline and remove legacy report"
```

**Success standard:** No file references the old `report_service.py`; full test suite green; README documents the new pipeline.

## Task 7: End-To-End Verification And Release Gate

**Files:**
- Modify: `README.md`
- Verify: all files changed in Tasks 1-6

- [ ] **Step 1: Run focused tests**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_alpha_analysis_run_models.py \
  tests/test_alpha_analysis_run_events.py \
  tests/test_alpha_analysis_run_service.py \
  tests/test_alpha_analysis_routes_v2.py \
  tests/test_alpha_routes.py \
  tests/test_dashboard_alpha_tab.py \
  tests/test_dashboard_page_contract.py \
  -q
```

Expected: all pass.

- [ ] **Step 2: Run full regression**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q
```

Expected: no new failures.

- [ ] **Step 3: Static checks and legacy scans**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/alpha src/api/routes_alpha.py
rg -n "AlphaPortfolioReportService|portfolio/report|alphaPortfolioSymbols|loadAlphaReport|alpha-report-include-shadow" src/alpha src/api/routes_alpha.py src/api/dashboard_page
```

Expected: ruff exits 0; rg exits 1 with no matches.

- [ ] **Step 4: Verify alembic heads**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m alembic heads
```

Expected: only `20260622_000021 (head)`.

- [ ] **Step 5: Verify production migration on server**

```bash
ssh ec2-user@13.214.201.113 "cd /home/ec2-user/a-share-hub && set -a && source .env && set +a && /home/ec2-user/miniconda3/envs/py311/bin/python -m alembic upgrade head && /home/ec2-user/miniconda3/envs/py311/bin/python -m alembic current"
```

Expected: `20260622_000021 (head)`.

- [ ] **Step 6: Restart service**

Kill the running uvicorn and relaunch with `.env` exported. Verify `/health` returns 200.

- [ ] **Step 7: Browser acceptance**

Viewport 1440×900:
1. Open http://13.214.201.113:8000/dashboard, log in.
2. Switch to US tab, add MU.US holding.
3. Click MU 分析 button — confirm accepted status appears within 1 second.
4. Watch stages progress: snapshot → research → trader → risk → backtest → completed.
5. Open drawer, verify cost, close P&L, final action.
6. Insert DeepSeek failure (invalid key), confirm run becomes failed with `error_stage` and no mock HOLD.
7. Generate 100+ runs, confirm fixed-height center, scroll pagination, drawer works.
8. Inspect browser console for errors.

- [ ] **Step 8: Commit docs after verification**

```bash
git add README.md
git commit -m "docs(alpha): streaming analysis release verification"
```

**Success standard:** All tests green, ruff clean, no legacy markers, single alembic head, server /health=200, browser acceptance passes, drawer focuses correctly on open/close.

## Final Acceptance Matrix

| Requirement | Owning task | Pass condition |
|---|---:|---|
| Single-symbol entry, one market-data fetch per run | 3, 4 | Service uses injected bars for all 5 stages |
| Stage-level SSE with cumulative payload | 2, 3, 4 | EventSource receives ordered updates; final event closes stream |
| Single active run per user | 3 | Same symbol returns existing run; different symbol returns 409 |
| Run lifecycle persistence | 1 | accepted → completed/failed states with `current_stage`, timestamps |
| List API is summary-only, cursor-paginated | 4 | `items` lack snapshot/research/trader/risk JSON; cursor present |
| Old `/portfolio/report` removed | 4, 6 | rg and tests confirm no references |
| Dashboard fixed height, drawer detail | 5 | 100 runs do not grow page; drawer shows full detail |
| Failed stages preserve earlier JSON | 3 | DeepSeek failure leaves snapshot/stages intact, no mock HOLD |
| User isolation | 1, 4 | Cross-user store and SSE tests return no records |
| No Yahoo rate-limit regression | 3 | Service fetches market data once and reuses; routes_alpha loader still wraps exceptions |
