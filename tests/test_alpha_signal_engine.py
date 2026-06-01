import pandas as pd

from src.alpha.signal_engine import AlphaSignalEngine


def test_signal_engine_scores_bullish_asset_as_buy():
    candles = pd.DataFrame(
        [
            {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1000},
            {"close": 102.0, "high": 103.0, "low": 101.0, "volume": 1100},
            {"close": 104.0, "high": 105.0, "low": 103.0, "volume": 1150},
            {"close": 106.0, "high": 107.0, "low": 105.0, "volume": 1200},
            {"close": 109.0, "high": 110.0, "low": 108.0, "volume": 1300},
        ]
    )
    engine = AlphaSignalEngine(buy_threshold=0.55, sell_threshold=-0.55)

    signal = engine.score_asset(symbol="AAPLx", candles=candles)

    assert signal.symbol == "AAPLx"
    assert signal.action == "BUY"
    assert signal.score >= 0.55
