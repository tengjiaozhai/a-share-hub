import pytest
import pandas as pd
import numpy as np
from src.crypto.strategy.indicators import CryptoIndicators

@pytest.fixture
def indicators():
    return CryptoIndicators()

@pytest.fixture
def sample_data():
    """创建样本数据"""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    np.random.seed(42)
    data = pd.DataFrame({
        'open': np.random.uniform(100, 200, 100),
        'high': np.random.uniform(200, 300, 100),
        'low': np.random.uniform(50, 100, 100),
        'close': np.random.uniform(100, 200, 100),
        'volume': np.random.uniform(1000000, 5000000, 100)
    }, index=dates)
    return data

def test_ma(indicators, sample_data):
    """测试移动平均"""
    ma5 = indicators.ma(sample_data['close'], 5)
    assert len(ma5) == len(sample_data)
    assert ma5.isna().sum() == 4  # 前4个值应该是NaN

def test_rsi(indicators, sample_data):
    """测试RSI指标"""
    rsi = indicators.rsi(sample_data['close'], 14)
    assert len(rsi) == len(sample_data)
    assert rsi.dropna().between(0, 100).all()

def test_macd(indicators, sample_data):
    """测试MACD指标"""
    macd = indicators.macd(sample_data['close'])
    assert 'macd' in macd
    assert 'signal' in macd
    assert 'histogram' in macd
    assert len(macd['macd']) == len(sample_data)

def test_bollinger(indicators, sample_data):
    """测试布林带"""
    bollinger = indicators.bollinger(sample_data['close'], 20)
    assert 'upper' in bollinger
    assert 'middle' in bollinger
    assert 'lower' in bollinger
    assert len(bollinger['upper']) == len(sample_data)

def test_atr(indicators, sample_data):
    """测试ATR指标"""
    atr = indicators.atr(sample_data, 14)
    assert len(atr) == len(sample_data)
    assert atr.dropna().ge(0).all()