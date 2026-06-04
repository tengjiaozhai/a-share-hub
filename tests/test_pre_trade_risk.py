from datetime import date

from src.risk.pre_trade_risk import evaluate_risk_gate


def test_risk_gate_blocks_kill_switch():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=True,
        available_cash=1_000_000,
        requested_value=100_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "kill_switch"


def test_risk_gate_blocks_position_limit():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="BUY",
        kill_switch=False,
        available_cash=1_000_000,
        requested_value=250_000,
        current_position_value=0,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=2_500,
        lot_size=100,
    )

    assert result["approved"] is False
    assert result["rule_name"] == "max_position_ratio"


def test_risk_gate_blocks_same_day_a_share_sell():
    result = evaluate_risk_gate(
        symbol="600519.SH",
        action="SELL",
        kill_switch=False,
        available_cash=1_000_000,
        requested_value=0,
        current_position_value=100_000,
        nav=1_000_000,
        max_position_ratio=0.2,
        quantity=100,
        lot_size=100,
        market="CN_A",
        buy_date=date(2026, 6, 4),
        trade_date=date(2026, 6, 4),
    )

    assert result["approved"] is False
    assert result["rule_name"] == "t_plus_one"
