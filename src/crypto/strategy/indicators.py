import pandas as pd
from typing import Dict


class CryptoIndicators:
    """加密货币技术指标"""

    def calculate_all(self, data: pd.DataFrame) -> Dict:
        """计算所有技术指标"""
        return {
            "ma5": self.ma(data['close'], 5),
            "ma10": self.ma(data['close'], 10),
            "ma20": self.ma(data['close'], 20),
            "ma60": self.ma(data['close'], 60),
            "rsi": self.rsi(data['close'], 14),
            "macd": self.macd(data['close']),
            "bollinger": self.bollinger(data['close'], 20),
            "atr": self.atr(data, 14),
            "volume_ma": self.ma(data['volume'], 20)
        }

    def ma(self, series: pd.Series, period: int) -> pd.Series:
        """移动平均"""
        return series.rolling(window=period).mean()

    def ema(self, series: pd.Series, period: int) -> pd.Series:
        """指数移动平均"""
        return series.ewm(span=period, adjust=False).mean()

    def rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """RSI指标"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def macd(self, series: pd.Series) -> Dict[str, pd.Series]:
        """MACD指标"""
        ema12 = self.ema(series, 12)
        ema26 = self.ema(series, 26)
        macd_line = ema12 - ema26
        signal_line = self.ema(macd_line, 9)
        histogram = macd_line - signal_line
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    def bollinger(self, series: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """布林带"""
        ma = self.ma(series, period)
        std = series.rolling(window=period).std()
        upper = ma + (std * 2)
        lower = ma - (std * 2)
        return {
            "upper": upper,
            "middle": ma,
            "lower": lower
        }

    def atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATR指标"""
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift(1))
        low_close = abs(data['low'] - data['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()

    def volatility(self, series: pd.Series, period: int = 20) -> pd.Series:
        """波动率"""
        return series.rolling(window=period).std() / series.rolling(window=period).mean()

    def volume_ratio(self, volume: pd.Series, period: int = 20) -> pd.Series:
        """成交量比率"""
        volume_ma = self.ma(volume, period)
        return volume / volume_ma
