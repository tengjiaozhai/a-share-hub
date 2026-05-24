import argparse
import sys

from fastapi import FastAPI

from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_decision_runs import router as decision_runs_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.api.routes_portfolio_targets import router as portfolio_targets_router
from src.api.routes_reconciliation import router as reconciliation_router
from src.api.routes_dashboard import router as dashboard_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(decision_runs_router)
    app.include_router(portfolio_targets_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(reconciliation_router)
    app.include_router(kill_switch_router)
    app.include_router(dashboard_router)
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

    # serve
    subparsers.add_parser("serve", help="启动API服务")

    return parser


def dispatch_command(args: argparse.Namespace) -> None:
    if args.command == "decide":
        print(f"decide: symbols={args.symbols}, mock_llm={args.mock_llm}")
    elif args.command == "shadow-execute":
        print(f"shadow-execute: symbols={args.symbols}, mock_broker={args.mock_broker}")
    elif args.command == "live-execute":
        print(f"live-execute: once={args.once}")
    elif args.command == "reconcile":
        print(f"reconcile: symbols={args.symbols}")
    elif args.command == "halt":
        print(f"halt: reason={args.reason}, resume={args.resume}")
    elif args.command == "serve" or args.command is None:
        import uvicorn
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
