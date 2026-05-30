import pytest
import pandas as pd
import numpy as np
from src.strategy.indicators import CryptoIndicators


@pytest.fixture
def indicators():
    return CryptoIndicators()


@pytest.fixture
def sample_data():
    """生成样本数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    close = 42000 + np.random.randn(100).cumsum() * 100
    high = close + abs(np.random.randn(100)) * 50
    low = close - abs(np.random.randn(100)) * 50
    volume = np.random.randint(1000, 10000, 100).astype(float)

    return pd.DataFrame({
        'close': close,
        'high': high,
        'low': low,
        'volume': volume
    }, index=dates)


def test_ma(indicators, sample_data):
    """测试移动平均"""
    ma5 = indicators.ma(sample_data['close'], 5)
    ma10 = indicators.ma(sample_data['close'], 10)

    assert len(ma5) == len(sample_data)
    assert len(ma10) == len(sample_data)
    assert ma5.iloc[-1] is not None
    assert ma10.iloc[-1] is not None


def test_rsi(indicators, sample_data):
    """测试RSI指标"""
    rsi = indicators.rsi(sample_data['close'], 14)

    assert len(rsi) == len(sample_data)
    assert 0 <= rsi.iloc[-1] <= 100


def test_macd(indicators, sample_data):
    """测试MACD指标"""
    macd = indicators.macd(sample_data['close'])

    assert "macd" in macd
    assert "signal" in macd
    assert "histogram" in macd
    assert len(macd["macd"]) == len(sample_data)


def test_bollinger(indicators, sample_data):
    """测试布林带"""
    bollinger = indicators.bollinger(sample_data['close'], 20)

    assert "upper" in bollinger
    assert "middle" in bollinger
    assert "lower" in bollinger
    assert len(bollinger["upper"]) == len(sample_data)


def test_atr(indicators, sample_data):
    """测试ATR指标"""
    atr = indicators.atr(sample_data, 14)

    assert len(atr) == len(sample_data)
    assert atr.iloc[-1] >= 0


def test_calculate_all(indicators, sample_data):
    """测试计算所有指标"""
    result = indicators.calculate_all(sample_data)

    assert "ma5" in result
    assert "ma10" in result
    assert "ma20" in result
    assert "ma60" in result
    assert "rsi" in result
    assert "macd" in result
    assert "bollinger" in result
    assert "atr" in result
    assert "volume_ma" in result
