from src.risk.pre_trade_risk import evaluate_risk_gate

def test_kill_switch_blocks_execution_plan():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=True,
        available_cash=500000,
        requested_value=100000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )
    assert result["approved"] is False
    assert result["reason"] == "kill switch enabled"

def test_insufficient_cash_blocks_buy():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=50000,
        requested_value=100000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )
    assert result["approved"] is False
    assert result["reason"] == "insufficient cash"

def test_approved_when_conditions_met():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=500000,
        requested_value=100000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )
    assert result["approved"] is True
