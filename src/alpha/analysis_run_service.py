from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from src.alpha.analysis_event_broadcaster import EventBroadcaster
from src.alpha.analysis_models import AnalysisSnapshot
from src.alpha.analysis_risk import evaluate_risk


class AlphaAnalysisNotFoundError(Exception):
    pass


class AlphaAnalysisConflictError(Exception):
    def __init__(self, active_run_id: str, active_symbol: str) -> None:
        super().__init__(f"active run {active_run_id} for {active_symbol} in progress")
        self.active_run_id = active_run_id
        self.active_symbol = active_symbol


def _market_of(symbol: str) -> str:
    return "us" if symbol.upper().endswith(".US") else "a"


def _lots_from_entries(entries: list[dict]) -> list[dict]:
    return [
        {
            "buy_price": float(e.get("buy_price", 0.0) or 0.0),
            "quantity": float(e.get("quantity", 0.0) or 0.0),
            "buy_date": e.get("buy_date"),
            "stop_loss_ratio": float(e.get("stop_loss_ratio", -0.08) or -0.08),
            "take_profit_ratio": float(e.get("take_profit_ratio", 0.20) or 0.20),
        }
        for e in entries
    ]


def _portfolio_market_value(entries: list[dict]) -> float:
    total = 0.0
    for e in entries:
        cost = float(e.get("buy_price", 0.0) or 0.0) * float(e.get("quantity", 0.0) or 0.0)
        total += cost
    return total


class AlphaAnalysisRunService:
    def __init__(
        self,
        *,
        store: Any,
        holdings_store: Any,
        snapshot_builder: Any,
        research_manager: Any,
        trader: Any,
        broadcaster: EventBroadcaster,
        user_id: str,
        model_name: str,
        max_position_ratio: float = 0.2,
        backtest_runner: Any | None = None,
    ) -> None:
        self._store = store
        self._holdings_store = holdings_store
        self._snapshot_builder = snapshot_builder
        self._research_manager = research_manager
        self._trader = trader
        self._broadcaster = broadcaster
        self._user_id = user_id
        self._model_name = model_name
        self._max_position_ratio = max_position_ratio
        self._backtest_runner = backtest_runner

    def start(self, request) -> dict:
        symbol = request.symbol
        entries = [e for e in self._holdings_store.list_alpha_holdings_entries() if str(e.get("symbol", "")).upper() == symbol.upper()]
        if not entries:
            raise AlphaAnalysisNotFoundError(f"no holding for {symbol}")

        active_for_symbol = self._store.find_active_run(symbol=symbol)
        if active_for_symbol:
            return {
                "run_id": active_for_symbol["run_id"],
                "symbol": active_for_symbol["symbol"],
                "market": _market_of(active_for_symbol["symbol"]),
                "status": active_for_symbol["status"],
                "stream_url": f"/api/v1/alpha/analysis-runs/{active_for_symbol['run_id']}/events",
                "created_at": active_for_symbol.get("created_at") or datetime.utcnow().isoformat(),
            }

        active_any = self._store.find_any_active_run()
        if active_any:
            raise AlphaAnalysisConflictError(active_any["run_id"], active_any["symbol"])

        run_id = self._store.create_run(symbol=symbol, model_name=self._model_name)
        self._store.append_event(run_id=run_id, stage="accepted", status="done", payload={"symbol": symbol}, event_type="accepted")
        return {
            "run_id": run_id,
            "symbol": symbol,
            "market": _market_of(symbol),
            "status": "accepted",
            "stream_url": f"/api/v1/alpha/analysis-runs/{run_id}/events",
            "created_at": datetime.utcnow().isoformat(),
        }

    async def execute(self, run_id: str) -> None:
        run = self._store.get_run(run_id)
        if not run:
            return
        symbol = run["symbol"]
        market = _market_of(symbol)
        entries = [e for e in self._holdings_store.list_alpha_holdings_entries() if str(e.get("symbol", "")).upper() == symbol.upper()]
        lots = _lots_from_entries(entries)
        portfolio_mv = _portfolio_market_value(entries)

        self._store.update_run(run_id, status="running", current_stage="snapshot")
        snapshot: Optional[AnalysisSnapshot] = None
        research: Optional[dict] = None
        trader_result: Optional[dict] = None
        risk: Optional[dict] = None
        backtest: Optional[dict] = None
        error_stage: Optional[str] = None
        error_message: Optional[str] = None

        try:
            self._store.append_event(run_id=run_id, stage="snapshot", status="started", payload={"symbol": symbol})
            snapshot = self._snapshot_builder.build(
                symbol=symbol, lots=lots, portfolio_market_value=portfolio_mv
            )
            self._store.update_run(run_id, snapshot=snapshot.model_dump())
            self._store.append_event(
                run_id=run_id,
                stage="snapshot",
                status="done",
                payload={"stage_payload": snapshot.model_dump()},
            )
            self._broadcast(run_id, market, "snapshot", "done", "快照已生成", snapshot=snapshot.model_dump())

            self._store.update_run(run_id, current_stage="research")
            self._store.append_event(run_id=run_id, stage="research", status="started")
            research_obj = self._research_manager.analyze(snapshot)
            research = research_obj.model_dump()
            self._store.update_run(run_id, research=research)
            self._store.append_event(run_id=run_id, stage="research", status="done", payload={"stage_payload": research})
            self._broadcast(run_id, market, "research", "done", "研究结论已生成", snapshot=snapshot.model_dump(), research=research)

            self._store.update_run(run_id, current_stage="trader")
            self._store.append_event(run_id=run_id, stage="trader", status="started")
            trader_obj = self._trader.propose(snapshot, research_obj)
            trader_result = trader_obj.model_dump()
            self._store.update_run(run_id, trader=trader_result)
            self._store.append_event(run_id=run_id, stage="trader", status="done", payload={"stage_payload": trader_result})
            self._broadcast(run_id, market, "trader", "done", "交易计划已生成", snapshot=snapshot.model_dump(), research=research, trader=trader_result)

            self._store.update_run(run_id, current_stage="risk")
            self._store.append_event(run_id=run_id, stage="risk", status="started")
            from src.alpha.analysis_models import ResearchPlan, TraderProposal
            risk_obj = evaluate_risk(
                snapshot,
                ResearchPlan.model_validate(research),
                TraderProposal.model_validate(trader_result),
                max_position_ratio=self._max_position_ratio,
            )
            risk = risk_obj.model_dump()
            self._store.update_run(run_id, risk=risk)
            self._store.append_event(run_id=run_id, stage="risk", status="done", payload={"stage_payload": risk})
            self._broadcast(run_id, market, "risk", "done", "风控结论已生成", snapshot=snapshot.model_dump(), research=research, trader=trader_result, risk=risk)

            self._store.update_run(run_id, current_stage="backtest")
            self._store.append_event(run_id=run_id, stage="backtest", status="started")
            backtest = self._run_backtest(snapshot, request=None)
            self._store.update_run(run_id, backtest=backtest)
            self._store.append_event(run_id=run_id, stage="backtest", status="done", payload={"stage_payload": backtest})
            self._broadcast(run_id, market, "backtest", "done", "回测完成", snapshot=snapshot.model_dump(), research=research, trader=trader_result, risk=risk, backtest=backtest)

            self._store.update_run(run_id, status="completed", current_stage="completed", finished_at=datetime.utcnow())
            self._store.append_event(run_id=run_id, stage="completed", status="done")
            self._broadcast(run_id, market, "completed", "done", "分析完成", snapshot=snapshot.model_dump(), research=research, trader=trader_result, risk=risk, backtest=backtest)

        except Exception as exc:
            error_stage = error_stage or "snapshot"
            error_message = str(exc)
            if snapshot and not research:
                error_stage = "research"
            elif snapshot and research and not trader_result:
                error_stage = "trader"
            elif snapshot and research and trader_result and not risk:
                error_stage = "risk"
            self._store.update_run(
                run_id,
                status="failed",
                current_stage="failed",
                error=error_message,
                error_stage=error_stage,
                finished_at=datetime.utcnow(),
            )
            self._store.append_event(run_id=run_id, stage="failed", status="done", payload={"stage": error_stage, "error": error_message})
            self._broadcast(
                run_id,
                market,
                "failed",
                "failed",
                error_message,
                error=error_message,
                error_stage=error_stage,
                snapshot=snapshot.model_dump() if snapshot else None,
                research=research,
                trader=trader_result,
                risk=risk,
                backtest=backtest,
            )

    def _run_backtest(self, snapshot: AnalysisSnapshot, request: Any | None) -> dict:
        if self._backtest_runner is None:
            return {"status": "skipped", "reason": "no backtest runner configured"}
        try:
            return self._backtest_runner(snapshot)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _broadcast(
        self,
        run_id: str,
        market: str,
        stage: str,
        status: str,
        message: str,
        *,
        snapshot: dict | None = None,
        research: dict | None = None,
        trader: dict | None = None,
        risk: dict | None = None,
        backtest: dict | None = None,
        error: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        seq = self._store.append_event(run_id=run_id, stage=stage, status=status, payload={
            "message": message,
            "snapshot": snapshot,
            "research": research,
            "trader": trader,
            "risk": risk,
            "backtest": backtest,
            "error": error,
            "error_stage": error_stage,
        }, event_type="stage")
        run = self._store.get_run(run_id)
        payload = {
            "run_id": run_id,
            "symbol": run["symbol"] if run else "",
            "market": market,
            "stage": stage,
            "status": status,
            "message": message,
            "snapshot": snapshot,
            "research": research,
            "trader": trader,
            "risk": risk,
            "backtest": backtest,
            "error": error,
            "error_stage": error_stage,
            "seq": seq,
        }
        self._broadcaster.publish(run_id, payload)