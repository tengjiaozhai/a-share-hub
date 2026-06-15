from src.core.market_rules import (
    calculate_lot_quantity,
    infer_market_from_symbol,
    is_limit_locked,
    is_sell_allowed,
    is_valid_lot_quantity,
    resolve_lot_size,
)


def test_infer_market_from_symbol_distinguishes_a_share_and_us():
    assert infer_market_from_symbol("600519.SH") == "CN_A"
    assert infer_market_from_symbol("000858.SZ") == "CN_A"
    assert infer_market_from_symbol("AAPL") == "US"
    assert infer_market_from_symbol("NVDA.US") == "US"


def test_resolve_lot_size_uses_split_market_settings():
    assert resolve_lot_size(symbol="600519.SH", lot_size_a=100, lot_size_us=1) == 100
    assert resolve_lot_size(symbol="AAPL", lot_size_a=100, lot_size_us=1) == 1
