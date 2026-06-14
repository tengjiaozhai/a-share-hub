from src.risk.pre_trade_risk import evaluate_risk_gate


def test_insufficient_cash_returns_structured_details():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=50_000,
        requested_value=100_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "cash"
    assert result["details"]["available_cash"] == 50_000
    assert result["details"]["requested_value"] == 100_000
