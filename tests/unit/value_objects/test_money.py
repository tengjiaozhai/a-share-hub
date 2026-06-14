import pytest
from decimal import Decimal
from src.domain.value_objects.money import Money


def test_create_money():
    """测试创建Money实例"""
    money = Money(Decimal("100.50"), "CNY")
    assert money.amount == Decimal("100.50")
    assert money.currency == "CNY"


def test_create_money_with_factory():
    """测试使用工厂方法创建Money"""
    money = Money.create(100.50, "CNY")
    assert money.amount == Decimal("100.50")
    assert money.currency == "CNY"


def test_create_zero_money():
    """测试创建零金额"""
    money = Money.zero("USD")
    assert money.amount == Decimal("0")
    assert money.currency == "USD"
    assert money.is_zero is True


def test_invalid_currency():
    """测试无效货币"""
    with pytest.raises(ValueError, match="不支持的货币"):
        Money(Decimal("100"), "INVALID")


def test_negative_amount():
    """测试负数金额"""
    with pytest.raises(ValueError, match="金额不能为负数"):
        Money(Decimal("-100"), "CNY")


def test_add_money():
    """测试金额加法"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("50"), "CNY")
    result = money1.add(money2)
    assert result.amount == Decimal("150")
    assert result.currency == "CNY"


def test_add_different_currency():
    """测试不同货币相加"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("50"), "USD")
    with pytest.raises(ValueError, match="货币不匹配"):
        money1.add(money2)


def test_subtract_money():
    """测试金额减法"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("50"), "CNY")
    result = money1.subtract(money2)
    assert result.amount == Decimal("50")


def test_subtract_result_negative():
    """测试减法结果为负数"""
    money1 = Money(Decimal("50"), "CNY")
    money2 = Money(Decimal("100"), "CNY")
    with pytest.raises(ValueError, match="结果不能为负数"):
        money1.subtract(money2)


def test_multiply_money():
    """测试金额乘法"""
    money = Money(Decimal("100"), "CNY")
    result = money.multiply(2.5)
    assert result.amount == Decimal("250.0")


def test_divide_money():
    """测试金额除法"""
    money = Money(Decimal("100"), "CNY")
    result = money.divide(4)
    assert result.amount == Decimal("25")


def test_divide_by_zero():
    """测试除以零"""
    money = Money(Decimal("100"), "CNY")
    with pytest.raises(ValueError, match="除数不能为零"):
        money.divide(0)


def test_round_money():
    """测试金额四舍五入"""
    money = Money(Decimal("100.555"), "CNY")
    result = money.round(2)
    assert result.amount == Decimal("100.56")


def test_money_equality():
    """测试金额相等性"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("100"), "CNY")
    money3 = Money(Decimal("100"), "USD")
    
    assert money1 == money2
    assert money1 != money3
    assert hash(money1) == hash(money2)


def test_money_comparison():
    """测试金额比较"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("200"), "CNY")
    
    assert money1 < money2
    assert money1 <= money2
    assert money2 > money1
    assert money2 >= money1


def test_money_comparison_different_currency():
    """测试不同货币比较"""
    money1 = Money(Decimal("100"), "CNY")
    money2 = Money(Decimal("100"), "USD")
    
    with pytest.raises(ValueError, match="货币不匹配"):
        money1 < money2


def test_money_str():
    """测试字符串表示"""
    money = Money(Decimal("100.50"), "CNY")
    assert str(money) == "100.50 CNY"
