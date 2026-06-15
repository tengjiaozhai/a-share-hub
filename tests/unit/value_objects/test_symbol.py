import pytest
from src.domain.value_objects.symbol import Symbol


def test_create_valid_symbol():
    """测试创建有效的股票代码"""
    symbol = Symbol("600519.SH")
    assert symbol.value == "600519.SH"
    assert symbol.code == "600519"
    assert symbol.market == "SH"
    assert symbol.is_shanghai is True
    assert symbol.is_shenzhen is False


def test_create_symbol_with_factory():
    """测试使用工厂方法创建股票代码"""
    symbol = Symbol.create("600519", "SH")
    assert symbol.value == "600519.SH"


def test_invalid_symbol_format():
    """测试无效的股票代码格式"""
    with pytest.raises(ValueError, match="无效的股票代码格式"):
        Symbol("invalid")


def test_empty_symbol():
    """测试空股票代码"""
    with pytest.raises(ValueError, match="股票代码不能为空"):
        Symbol("")


def test_symbol_immutability():
    """测试股票代码不可变性"""
    symbol = Symbol("600519.SH")
    with pytest.raises(AttributeError):
        symbol.value = "000001.SZ"


def test_symbol_equality():
    """测试股票代码相等性"""
    symbol1 = Symbol("600519.SH")
    symbol2 = Symbol("600519.SH")
    symbol3 = Symbol("000001.SZ")
    
    assert symbol1 == symbol2
    assert symbol1 != symbol3
    assert hash(symbol1) == hash(symbol2)


def test_shenzhen_symbol():
    """测试深圳市场股票代码"""
    symbol = Symbol("000001.SZ")
    assert symbol.is_shenzhen is True
    assert symbol.is_shanghai is False


def test_beijing_symbol():
    """测试北京市场股票代码"""
    symbol = Symbol("430047.BJ")
    assert symbol.is_beijing is True
