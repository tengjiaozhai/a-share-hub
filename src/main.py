import argparse
import sys

from fastapi import FastAPI

from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.api.routes_dashboard import router as dashboard_router


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(kill_switch_router)
    app.include_router(dashboard_router)
    return app


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a-share-hub", description="A股自动交易系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # sync-market
    p_sync = subparsers.add_parser("sync-market", help="同步市场数据")
    p_sync.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_sync.add_argument("--interval", default="daily", help="数据周期")
    p_sync.add_argument("--limit", type=int, default=100, help="数据条数")

    # build-features
    p_feat = subparsers.add_parser("build-features", help="构建技术特征")
    p_feat.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_feat.add_argument("--top-n", type=int, default=10, help="Top N 特征")

    # run-decision
    p_dec = subparsers.add_parser("run-decision", help="运行决策")
    p_dec.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_dec.add_argument("--mock-llm", action="store_true", help="使用模拟LLM")

    # plan-execution
    p_plan = subparsers.add_parser("plan-execution", help="规划执行计划")
    p_plan.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_plan.add_argument("--nav", type=float, required=True, help="净资产值")

    # shadow-execute
    p_shadow = subparsers.add_parser("shadow-execute", help="影子执行")
    p_shadow.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")
    p_shadow.add_argument("--mock-broker", action="store_true", help="使用模拟券商")

    # reconcile
    p_recon = subparsers.add_parser("reconcile", help="对账")
    p_recon.add_argument("--symbols", nargs="+", required=True, help="股票代码列表")

    # serve
    subparsers.add_parser("serve", help="启动API服务")

    return parser


def dispatch_command(args: argparse.Namespace) -> None:
    if args.command == "sync-market":
        print(f"sync-market: symbols={args.symbols}, interval={args.interval}, limit={args.limit}")
    elif args.command == "build-features":
        print(f"build-features: symbols={args.symbols}, top_n={args.top_n}")
    elif args.command == "run-decision":
        print(f"run-decision: symbols={args.symbols}, mock_llm={args.mock_llm}")
    elif args.command == "plan-execution":
        print(f"plan-execution: symbols={args.symbols}, nav={args.nav}")
    elif args.command == "shadow-execute":
        print(f"shadow-execute: symbols={args.symbols}, mock_broker={args.mock_broker}")
    elif args.command == "reconcile":
        print(f"reconcile: symbols={args.symbols}")
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
