import pytest
from decimal import Decimal
from src.domain.value_objects.percentage import Percentage


def test_create_percentage():
    """测试创建Percentage实例"""
    percentage = Percentage(Decimal("50"))
    assert percentage.value == Decimal("50")


def test_create_percentage_with_factory():
    """测试使用工厂方法创建Percentage"""
    percentage = Percentage.create(75.5)
    assert percentage.value == Decimal("75.5")


def test_create_from_ratio():
    """测试从比率创建百分比"""
    percentage = Percentage.from_ratio(0.75)
    assert percentage.value == Decimal("75.0")


def test_create_zero_percentage():
    """测试创建零百分比"""
    percentage = Percentage.zero()
    assert percentage.value == Decimal("0")
    assert percentage.is_zero is True


def test_create_hundred_percentage():
    """测试创建100%"""
    percentage = Percentage.hundred()
    assert percentage.value == Decimal("100")
    assert percentage.is_hundred is True


def test_invalid_percentage_below_zero():
    """测试低于0%的百分比"""
    with pytest.raises(ValueError, match="百分比必须在0-100之间"):
        Percentage(Decimal("-10"))


def test_invalid_percentage_above_hundred():
    """测试高于100%的百分比"""
    with pytest.raises(ValueError, match="百分比必须在0-100之间"):
        Percentage(Decimal("110"))


def test_ratio_property():
    """测试比率属性"""
    percentage = Percentage(Decimal("75"))
    assert percentage.ratio == Decimal("0.75")


def test_add_percentage():
    """测试百分比加法"""
    p1 = Percentage(Decimal("30"))
    p2 = Percentage(Decimal("20"))
    result = p1.add(p2)
    assert result.value == Decimal("50")


def test_add_percentage_exceeds_hundred():
    """测试加法超过100%"""
    p1 = Percentage(Decimal("80"))
    p2 = Percentage(Decimal("30"))
    with pytest.raises(ValueError, match="结果超过100%"):
        p1.add(p2)


def test_subtract_percentage():
    """测试百分比减法"""
    p1 = Percentage(Decimal("80"))
    p2 = Percentage(Decimal("30"))
    result = p1.subtract(p2)
    assert result.value == Decimal("50")


def test_subtract_percentage_below_zero():
    """测试减法低于0%"""
    p1 = Percentage(Decimal("30"))
    p2 = Percentage(Decimal("80"))
    with pytest.raises(ValueError, match="结果低于0%"):
        p1.subtract(p2)


def test_multiply_percentage():
    """测试百分比乘法"""
    percentage = Percentage(Decimal("50"))
    result = percentage.multiply(2)
    assert result.value == Decimal("100")


def test_multiply_percentage_exceeds_hundred():
    """测试乘法超过100%"""
    percentage = Percentage(Decimal("80"))
    with pytest.raises(ValueError, match="结果超过100%"):
        percentage.multiply(2)


def test_apply_to_amount():
    """测试应用百分比到金额"""
    percentage = Percentage(Decimal("20"))
    amount = Decimal("1000")
    result = percentage.apply_to(amount)
    assert result == Decimal("200.0")


def test_round_percentage():
    """测试百分比四舍五入"""
    percentage = Percentage(Decimal("33.333"))
    result = percentage.round(2)
    assert result.value == Decimal("33.33")


def test_percentage_equality():
    """测试百分比相等性"""
    p1 = Percentage(Decimal("50"))
    p2 = Percentage(Decimal("50"))
    p3 = Percentage(Decimal("75"))
    
    assert p1 == p2
    assert p1 != p3
    assert hash(p1) == hash(p2)


def test_percentage_comparison():
    """测试百分比比较"""
    p1 = Percentage(Decimal("30"))
    p2 = Percentage(Decimal("70"))
    
    assert p1 < p2
    assert p1 <= p2
    assert p2 > p1
    assert p2 >= p1


def test_percentage_str():
    """测试字符串表示"""
    percentage = Percentage(Decimal("75.5"))
    assert str(percentage) == "75.5%"
