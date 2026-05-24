from src.api.routes_execution_plans import serialize_execution_plan


def test_execution_plan_payload_contains_client_order_key():
    payload = serialize_execution_plan(
        {"plan_id": "P1", "symbol": "600519.SH", "target_value": 100000, "action": "BUY", "reason": "test"}
    )
    assert payload["plan_id"] == "P1"
    assert payload["symbol"] == "600519.SH"
