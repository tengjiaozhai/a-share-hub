import argparse

import requests

from windows_agent.local_risk_check import local_gate
from windows_agent.xtquant_adapter import XtQuantAdapter


def run_once(base_url: str) -> int:
    """单次轮询执行"""
    adapter = XtQuantAdapter()
    adapter.connect()

    response = requests.get(f"{base_url}/api/v1/execution-plans/ready", timeout=5)
    response.raise_for_status()
    plans = response.json()

    processed = 0
    for plan in plans:
        gate = local_gate(
            trader_connected=adapter.connected,
            available_cash=1_000_000,
            requested_value=plan.get("target_value", 0),
            requested_quantity=plan.get("quantity", 0),
            available_sell_quantity=plan.get("available_sell_quantity", 0),
            action=plan.get("action", "BUY"),
        )
        if not gate["approved"]:
            continue

        broker_result = adapter.submit_order(plan)
        requests.post(
            f"{base_url}/api/v1/broker-events",
            json={
                "event_id": f"evt-{plan.get('plan_id', 'unknown')}",
                "order_id": plan.get("plan_id", "unknown"),
                "event_type": broker_result.get("status", "SUBMITTED"),
                "payload": broker_result,
            },
            timeout=5,
        ).raise_for_status()

        requests.post(
            f"{base_url}/api/v1/execution-plans/{plan.get('plan_id')}/ack",
            timeout=5,
        ).raise_for_status()
        processed += 1

    adapter.disconnect()
    return processed


def main():
    parser = argparse.ArgumentParser(description="Windows轮询执行器")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API服务地址")
    parser.add_argument("--once", action="store_true", help="单次执行")
    args = parser.parse_args()

    if args.once:
        processed = run_once(args.base_url)
        print(f"processed {processed} plans")
    else:
        print("持续轮询模式需要 --once 参数")


if __name__ == "__main__":
    main()
