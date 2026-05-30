import pytest
from src.core.config import Config
from src.core.enums import OrderSide, OrderType

def test_config_initialization():
    """测试配置初始化"""
    config = Config()
    assert config.binance is not None
    assert config.trading is not None

def test_enums():
    """测试枚举定义"""
    assert OrderSide.BUY == "BUY"
    assert OrderType.LIMIT == "LIMIT"