import pytest
from src.core.market_rules import can_sell_position_same_day, get_price_limit_ratio, is_tradable

class TestMarketRules:
    def test_can_sell_position_same_day_cn_a(self):
        """测试A股T+1规则"""
        assert can_sell_position_same_day("CN_A") is False

    def test_can_sell_position_same_day_us(self):
        """测试美股T+0规则"""
        assert can_sell_position_same_day("US") is True

    def test_get_price_limit_ratio_normal(self):
        """测试普通股票涨跌停比例"""
        assert get_price_limit_ratio("normal") == 0.10

    def test_get_price_limit_ratio_st(self):
        """测试ST股票涨跌停比例"""
        assert get_price_limit_ratio("ST") == 0.05

    def test_is_tradable_normal(self):
        """测试正常交易状态"""
        assert is_tradable("正常交易") is True

    def test_is_tradable_trading(self):
        """测试trading状态"""
        assert is_tradable("trading") is True

    def test_is_tradable_suspended(self):
        """测试停牌状态"""
        assert is_tradable("停牌") is False

    def test_is_tradable_delisted(self):
        """测试退市状态"""
        assert is_tradable("退市") is False


from datetime import date

from src.core.market_rules import (
    calculate_lot_quantity,
    is_limit_locked,
    is_sell_allowed,
    is_valid_lot_quantity,
)


def test_calculate_lot_quantity_rounds_down_to_a_share_lot():
    assert calculate_lot_quantity(target_value=20_000, price=103.0, lot_size=100) == 100
    assert calculate_lot_quantity(target_value=9_000, price=103.0, lot_size=100) == 0


def test_valid_lot_quantity_rejects_odd_lot_buy():
    assert is_valid_lot_quantity("BUY", 100, lot_size=100) is True
    assert is_valid_lot_quantity("BUY", 150, lot_size=100) is False
    assert is_valid_lot_quantity("SELL", 150, lot_size=100) is True


def test_sell_allowed_blocks_same_day_a_share_sell():
    assert is_sell_allowed("CN_A", buy_date=date(2026, 6, 4), sell_date=date(2026, 6, 4)) is False
    assert is_sell_allowed("CN_A", buy_date=date(2026, 6, 3), sell_date=date(2026, 6, 4)) is True
    assert is_sell_allowed("US", buy_date=date(2026, 6, 4), sell_date=date(2026, 6, 4)) is True


def test_limit_locked_blocks_buy_at_limit_up_and_sell_at_limit_down():
    assert is_limit_locked(action="BUY", current_price=110.0, prev_close=100.0, limit_ratio=0.10) is True
    assert is_limit_locked(action="SELL", current_price=90.0, prev_close=100.0, limit_ratio=0.10) is True
    assert is_limit_locked(action="BUY", current_price=108.0, prev_close=100.0, limit_ratio=0.10) is False
