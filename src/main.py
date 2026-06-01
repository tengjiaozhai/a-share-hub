import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import sys

from fastapi import FastAPI

from src.agents.llm_client import LLMClient
from src.core.config import Settings
from src.decision.decision_runner import build_decision_run_record
from src.decision.input_builder import build_decision_input_snapshot
from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_crypto import router as crypto_router
from src.api.routes_decision_runs import router as decision_runs_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.api.routes_portfolio_targets import router as portfolio_targets_router
from src.api.routes_reconciliation import router as reconciliation_router
from src.api.routes_market import router as market_router
from src.api.routes_dashboard import router as dashboard_router
from src.portfolio.target_planner import build_target_position
from src.storage.dependencies import get_runtime_store


def run_decide_command(symbols: list[str], mock_llm: bool, store=None) -> dict:
    runtime_store = store or get_runtime_store()
    if runtime_store.get_kill_switch():
        return {"status": "blocked", "reason": "kill switch enabled", "decision_run_ids": [], "target_position_ids": []}

    client = LLMClient(Settings(llm_provider="mock", llm_api_key="")) if mock_llm else LLMClient()
    decision_run_ids: list[str] = []
    target_position_ids: list[str] = []

    for symbol in symbols:
        prompt = f"Generate a shadow trading decision for {symbol}."
        input_snapshot = build_decision_input_snapshot(
            symbol=symbol,
            features={"source": "cli", "mock_llm": mock_llm},
            market_context={"mode": "shadow"},
        )
        raw_output = client.generate(prompt)
        if raw_output is None:
            raise RuntimeError("LLM client returned no output")

        record = build_decision_run_record(
            raw=raw_output,
            symbol=symbol,
            prompt_hash=sha256(prompt.encode("utf-8")).hexdigest(),
            input_snapshot=input_snapshot,
            model_name=client.model,
        )
        decision_run_id = runtime_store.insert_decision_run(**record)
        decision_run_ids.append(decision_run_id)

        if record["parsed_action"] in {"BUY", "SELL"} and record["target_position_ratio"] > 0:
            target = build_target_position(
                symbol=symbol,
                action=record["parsed_action"],
                target_position_ratio=record["target_position_ratio"],
                net_asset_value=1_000_000.0,
                expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
            )
            target_position_id = runtime_store.insert_target_position(
                decision_run_id=decision_run_id,
                symbol=target["symbol"],
                action=target["action"],
                target_value=target["target_value"],
                target_position_ratio=target["target_position_ratio"],
                expires_at=target["expires_at"],
            )
            target_position_ids.append(target_position_id)

    return {
        "status": "ok",
        "decision_run_ids": decision_run_ids,
        "target_position_ids": target_position_ids,
    }


def run_halt_command(reason: str, resume: bool, store=None) -> dict:
    runtime_store = store or get_runtime_store()
    active = not resume
    runtime_store.insert_kill_switch_event(active=active, reason=reason)
    return {"status": "ok", "active": active, "reason": reason, "resume": resume}


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(decision_runs_router)
    app.include_router(portfolio_targets_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(reconciliation_router)
    app.include_router(kill_switch_router)
    app.include_router(market_router)
    app.include_router(dashboard_router)
    app.include_router(crypto_router)
    return app


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a-share-hub", description="A股自动交易系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # decide
    p_decide = subparsers.add_parser("decide", help="运行决策并持久化结果")
    p_decide.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_decide.add_argument("--mock-llm", action="store_true", help="使用模拟LLM")

    # shadow-execute
    p_shadow = subparsers.add_parser("shadow-execute", help="影子执行")
    p_shadow.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_shadow.add_argument("--mock-broker", action="store_true", help="使用模拟券商")

    # live-execute
    p_live = subparsers.add_parser("live-execute", help="Windows 实盘执行")
    p_live.add_argument("--once", action="store_true", help="单次执行")

    # reconcile
    p_recon = subparsers.add_parser("reconcile", help="对账")
    p_recon.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")

    # halt
    p_halt = subparsers.add_parser("halt", help="触发或恢复停机")
    p_halt.add_argument("--reason", required=True, help="停机原因")
    p_halt.add_argument("--resume", action="store_true", help="恢复运行")

    # backtest
    p_backtest = subparsers.add_parser("backtest", help="运行日频回测")
    p_backtest.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_backtest.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    p_backtest.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")

    # evaluate-shadow
    p_eval = subparsers.add_parser("evaluate-shadow", help="运行长期 shadow 评估")
    p_eval.add_argument("--window", choices=["1m", "3m", "1y"], required=True, help="评估窗口")

    # serve
    subparsers.add_parser("serve", help="启动API服务")

    return parser


def dispatch_command(args: argparse.Namespace) -> None:
    if args.command == "decide":
        summary = run_decide_command(args.symbols, args.mock_llm)
        if summary["status"] == "blocked":
            print(f"decide: blocked ({summary['reason']})")
        else:
            print(
                f"decide: persisted {len(summary['decision_run_ids'])} runs, "
                f"{len(summary['target_position_ids'])} targets"
            )
    elif args.command == "shadow-execute":
        print(f"shadow-execute: symbols={args.symbols}, mock_broker={args.mock_broker}")
    elif args.command == "live-execute":
        print(f"live-execute: once={args.once}")
    elif args.command == "reconcile":
        print(f"reconcile: symbols={args.symbols}")
    elif args.command == "halt":
        summary = run_halt_command(args.reason, args.resume)
        state = "resumed" if summary["active"] is False else "halted"
        print(f"halt: {state}, reason={summary['reason']}")
    elif args.command == "backtest":
        print(f"backtest: symbols={args.symbols} start={args.start} end={args.end}")
    elif args.command == "evaluate-shadow":
        from src.evaluation.long_run import run_long_horizon_evaluation
        store = get_runtime_store()
        result = run_long_horizon_evaluation(store=store, window=args.window, mode="shadow")
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "serve" or args.command is None:
        import logging
        import uvicorn
        logging.basicConfig(level=logging.INFO)
        app = build_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print(f"未知命令: {args.command}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = build_cli_parser()
    args = parser.parse_args()
    dispatch_command(args)


if __name__ == "__main__":
    main()

# ASGI app for uvicorn
app = build_app()
