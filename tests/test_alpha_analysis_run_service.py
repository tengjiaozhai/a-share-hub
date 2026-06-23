import asyncio
import pytest

from src.alpha.analysis_event_broadcaster import EventBroadcaster
from src.alpha.analysis_run_models import AnalysisRunCreateRequest
from src.alpha.analysis_run_service import AlphaAnalysisConflict, AlphaAnalysisNotFound, AlphaAnalysisRunService


class FakeStore:
    """Mimics AnalysisRunStore contract used by AlphaAnalysisRunService."""

    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.events: dict[str, list[dict]] = {}
        self.seq_counter: dict[str, int] = {}

    def find_active_run(self, *, symbol=None):
        for run in self.runs.values():
            if run["status"] in {"accepted", "running"} and (symbol is None or run["symbol"] == symbol):
                return dict(run)
        return None

    def find_any_active_run(self):
        return self.find_active_run(symbol=None)

    def create_run(self, *, symbol, model_name):
        run_id = f"alpha-ar-{len(self.runs) + 1}"
        self.runs[run_id] = {
            "run_id": run_id,
            "symbol": symbol,
            "status": "accepted",
            "current_stage": "accepted",
            "model_name": model_name,
            "snapshot": None,
            "research": None,
            "trader": None,
            "risk": None,
            "backtest": None,
            "error": None,
            "error_stage": None,
        }
        self.events[run_id] = []
        self.seq_counter[run_id] = 0
        return run_id

    def update_run(self, run_id, **fields):
        self.runs[run_id].update(fields)

    def append_event(self, *, run_id, stage, status, payload=None, event_type="stage"):
        self.seq_counter[run_id] += 1
        seq = self.seq_counter[run_id]
        self.events[run_id].append({"seq": seq, "stage": stage, "status": status, "payload": payload or {}})
        return seq

    def get_run(self, run_id):
        return self.runs.get(run_id)


class FakeHoldingsStore:
    def __init__(self, entries):
        self.entries = entries

    def list_alpha_holdings_entries(self):
        return self.entries


class FakeLLM:
    def generate_json(self, *, system_prompt, user_prompt, temperature=0.2, max_tokens=1000):
        if "持仓研究经理" in system_prompt:
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

    def build(self, *, symbol, lots, portfolio_market_value):
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


def test_start_returns_accepted_payload_with_stream_url():
    from src.alpha.analysis_agents import ResearchManager, Trader
    service = AlphaAnalysisRunService(
        store=FakeStore(),
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
    assert response["symbol"] == "MU.US"


def test_execute_runs_all_stages_and_persists():
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
    asyncio.run(service.execute(response["run_id"]))

    run = store.get_run(response["run_id"])
    assert run["status"] == "completed"
    assert run["current_stage"] == "completed"
    assert run["risk"]["action"] == "ADD"
    stage_sequence = [e["stage"] for e in store.events[response["run_id"]]]
    assert stage_sequence[0] == "accepted"
    assert "snapshot" in stage_sequence
    assert "research" in stage_sequence
    assert "trader" in stage_sequence
    assert "risk" in stage_sequence
    assert "backtest" in stage_sequence
    assert stage_sequence[-1] == "completed"


def test_repeat_request_for_same_symbol_returns_existing_run():
    service = AlphaAnalysisRunService(
        store=FakeStore(),
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=None,
        trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    first = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    second = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    assert first["run_id"] == second["run_id"]


def test_other_symbol_while_active_returns_conflict():
    service = AlphaAnalysisRunService(
        store=FakeStore(),
        holdings_store=FakeHoldingsStore([
            {"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"},
            {"symbol": "MSFT.US", "buy_price": 200.0, "quantity": 5, "buy_date": "2026-01-01"},
        ]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=None,
        trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    first = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    with pytest.raises(AlphaAnalysisConflict) as exc:
        service.start(AnalysisRunCreateRequest(symbol="MSFT.US", backtest_window="60d", include_backtest=True))
    assert exc.value.active_run_id == first["run_id"]


def test_unknown_symbol_raises_not_found():
    service = AlphaAnalysisRunService(
        store=FakeStore(),
        holdings_store=FakeHoldingsStore([{"symbol": "OTHER", "buy_price": 1.0, "quantity": 1, "buy_date": "2026-01-01"}]),
        snapshot_builder=FakeSnapshotBuilder(_make_snapshot()),
        research_manager=None,
        trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    with pytest.raises(AlphaAnalysisNotFound):
        service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))


def test_snapshot_builder_called_only_once():
    from src.alpha.analysis_agents import ResearchManager, Trader
    builder = FakeSnapshotBuilder(_make_snapshot())
    store = FakeStore()
    service = AlphaAnalysisRunService(
        store=store,
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}]),
        snapshot_builder=builder,
        research_manager=ResearchManager(FakeLLM()),
        trader=Trader(FakeLLM()),
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    response = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    asyncio.run(service.execute(response["run_id"]))
    assert builder.calls == 1


def test_deepseek_failure_marks_failed_preserves_snapshot():
    from src.alpha.analysis_agents import AnalysisAgentError, ResearchManager

    class FailingResearchManager(ResearchManager):
        def __init__(self):
            pass
        def analyze(self, snapshot):
            raise AnalysisAgentError("DeepSeek timeout")

    builder = FakeSnapshotBuilder(_make_snapshot())
    store = FakeStore()
    service = AlphaAnalysisRunService(
        store=store,
        holdings_store=FakeHoldingsStore([{"symbol": "MU.US", "buy_price": 100.0, "quantity": 10, "buy_date": "2026-01-01"}]),
        snapshot_builder=builder,
        research_manager=FailingResearchManager(),
        trader=None,
        broadcaster=EventBroadcaster(),
        user_id="alice",
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    response = service.start(AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True))
    asyncio.run(service.execute(response["run_id"]))
    run = store.get_run(response["run_id"])
    assert run["status"] == "failed"
    assert run["error_stage"] == "research"
    assert "DeepSeek timeout" in run["error"]
    assert run["snapshot"] == _make_snapshot().model_dump()
    assert run["research"] is None
    assert run["risk"] is None