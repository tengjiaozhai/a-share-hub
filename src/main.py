import argparse
import sys
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse

from src.a_stock.routes import router as a_stock_router
from src.agents.llm_client import LLMClient
from src.api.auth_security import auth_middleware
from src.api.routes_alpha import router as alpha_router
from src.api.routes_auth import router as auth_router
from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_crypto import router as crypto_router
from src.api.routes_dashboard import router as dashboard_router
from src.api.routes_decision_runs import router as decision_runs_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_fund import router as fund_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.api.routes_market import router as market_router
from src.api.routes_portfolio_targets import router as portfolio_targets_router
from src.api.routes_reconciliation import router as reconciliation_router
from src.core.config import Settings
from src.core.tenant import SYSTEM_TENANT
from src.decision.decision_runner import build_decision_run_record
from src.decision.input_builder import build_decision_input_snapshot
from src.portfolio.target_planner import build_target_position
from src.storage.dependencies import get_runtime_engine
from src.storage.runtime_store import RuntimeStore
from src.storage.system_runtime_store import SystemRuntimeStore
from src.us_stock.routes import router as us_stock_router

_FAVICON_PATH = Path(__file__).resolve().parent / "api" / "static" / "favicon.ico"

# CLI 命令在用户未登录时使用 system 账户执行
CLI_USER_ID = SYSTEM_TENANT.user_id


def _system_store() -> SystemRuntimeStore:
    return SystemRuntimeStore(get_runtime_engine())


def run_decide_command(symbols: list[str], mock_llm: bool, store=None) -> dict:
    runtime_store = store if isinstance(store, RuntimeStore) else RuntimeStore(get_runtime_engine(), SYSTEM_TENANT)
    system_store = SystemRuntimeStore(runtime_store.engine)
    if system_store.get_kill_switch():
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
                capital_base=1_000_000.0,
                max_position_ratio=0.2,
                watchlist_size=len(symbols),
                price=100.0,
                lot_size=100,
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
    system_store = store if isinstance(store, SystemRuntimeStore) else _system_store()
    active = not resume
    system_store.insert_kill_switch_event(
        actor_user_id=SYSTEM_TENANT.user_id, active=active, reason=reason
    )
    return {"status": "ok", "active": active, "reason": reason, "resume": resume}


def build_app() -> FastAPI:
    app = FastAPI(title="trading-assistant")
    app.middleware("http")(auth_middleware)
    app.include_router(auth_router)
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
    app.include_router(alpha_router)
    app.include_router(us_stock_router)
    app.include_router(a_stock_router)
    app.include_router(fund_router)

    @app.get("/", include_in_schema=False)
    def root_redirect(request: Request):
        return RedirectResponse(url="/dashboard" if getattr(request.state, "user", None) else "/login")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(str(_FAVICON_PATH), media_type="image/vnd.microsoft.icon")

    settings = Settings()
    if settings.enable_scheduler or settings.app_role == "scheduler":
        _register_scheduler_lifecycle(app)
    else:
        _register_app_lifespan(app)

    return app


def _register_app_lifespan(app: FastAPI) -> None:
    """注册应用生命周期：启动 backfill、调度器；关闭时 dispose 引擎连接池。

    防御层 3：lifespan shutdown 显式 dispose 引擎，避免 `pkill -9` 残留 idle-in-tx 连接。
    """
    from contextlib import asynccontextmanager

    from src.scheduler.daily_scheduler import get_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = get_scheduler()
        scheduler.start()
        try:
            _run_startup_backfill()
            yield
        finally:
            try:
                scheduler.stop()
            except Exception:
                pass
            # 防御层 3：graceful shutdown 释放所有连接池中的连接
            try:
                get_runtime_engine().dispose()
            except Exception:
                pass

    app.router.lifespan_context = lifespan


def _register_scheduler_lifecycle(app: FastAPI) -> None:
    """仅调度器进程使用：保留旧 lifespan 兼容（即将废弃）"""
    _register_app_lifespan(app)


def _run_startup_backfill() -> None:
    """启动时检查 auto 账户是否需要 backfill"""
    try:
        from sqlalchemy.orm import Session

        from src.paper_ledger.backfill import backfill_recent_days, needs_backfill
        from src.paper_ledger.store import PaperLedgerStore

        engine = get_runtime_engine()
        with Session(engine) as session:
            store = PaperLedgerStore(session, SYSTEM_TENANT)
            today = datetime.utcnow().date()
            for market in ("a", "us"):
                job_key = store.acquire_job_lock("startup_backfill", market, today, ttl_seconds=3600)
                if job_key is None:
                    continue
                try:
                    if needs_backfill(store, market):
                        backfill_recent_days(store, market, days=30)
                    store.finish_job_lock(job_key, "success")
                except Exception as e:
                    store.finish_job_lock(job_key, "failed", str(e))
                    raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"startup backfill failed: {e}")


async def run_scheduler_forever() -> None:
    """运行独立调度器进程。"""
    from src.scheduler.daily_scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler.start()
    try:
        _run_startup_backfill()
        import asyncio

        await asyncio.Event().wait()
    finally:
        scheduler.stop()


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

    # scheduler
    subparsers.add_parser("scheduler", help="启动独立日频调度器")

    # set-user-role
    role_parser = subparsers.add_parser("set-user-role", help="显式赋予用户角色")
    role_parser.add_argument("--user-id", required=True)
    role_parser.add_argument("--role", required=True, choices=("user", "admin"))

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

        store = RuntimeStore(get_runtime_engine(), SYSTEM_TENANT)
        result = run_long_horizon_evaluation(store=store, window=args.window, mode="shadow")
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "scheduler":
        import asyncio
        import logging

        logging.basicConfig(level=logging.INFO)
        asyncio.run(run_scheduler_forever())
    elif args.command == "set-user-role":
        from src.storage.auth_store import AuthStore

        store = AuthStore(get_runtime_engine())
        if not store.set_role(args.user_id, args.role):
            raise SystemExit(f"user not found: {args.user_id}")
        print(f"updated {args.user_id} role to {args.role}")
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
