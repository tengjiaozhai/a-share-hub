from src.indicators.technical_indicators import compute_feature_row
from src.strategy.signal_engine import build_signal, compute_technical_score
from src.strategy.strategy_config import StrategyConfig

_BASE_CONFIG = StrategyConfig(
    top_n=10,
    max_position_ratio=0.2,
    buy_score_threshold=0.55,
    sell_score_threshold=-0.20,
)


def test_compute_feature_row_returns_extended_feature_set():
    close_prices = [100 + i for i in range(80)]

    row = compute_feature_row(close_prices)

    assert set(row) >= {
        "ma20_gap",
        "ma60_gap",
        "momentum_20",
        "momentum_60",
        "rsi_14",
        "volatility_20",
    }


def test_build_signal_returns_buy_for_high_score():
    # 确保评分 >= 0.55：momentum_20*0.30 + momentum_60*0.25 + ma20_gap*0.20 + ma60_gap*0.15 + vol*0.10 - vola*0.10
    # = 0.80*0.30 + 0.60*0.25 + 0.50*0.20 + 0.40*0.15 + 1.5*0.10 - 0.01*0.10
    # = 0.24 + 0.15 + 0.10 + 0.06 + 0.15 - 0.001 = 0.699
    features = {
        "ma20_gap": 0.50,
        "ma60_gap": 0.40,
        "momentum_20": 0.80,
        "momentum_60": 0.60,
        "rsi_14": 58,
        "volatility_20": 0.01,
        "volume_ratio_20": 1.50,
    }

    signal = build_signal("600519.SH", features, _BASE_CONFIG)

    assert signal["action"] == "BUY"
    assert signal["technical_score"] >= 0.55


def test_build_signal_returns_sell_for_high_rsi():
    features = {
        "ma20_gap": 0.02,
        "ma60_gap": 0.01,
        "momentum_20": 0.05,
        "momentum_60": 0.03,
        "rsi_14": 82,
        "volatility_20": 0.02,
        "volume_ratio_20": 1.0,
    }

    signal = build_signal("000858.SZ", features, _BASE_CONFIG)

    assert signal["action"] == "SELL"


def test_build_signal_returns_hold_for_neutral():
    features = {
        "ma20_gap": 0.01,
        "ma60_gap": 0.005,
        "momentum_20": 0.02,
        "momentum_60": 0.01,
        "rsi_14": 55,
        "volatility_20": 0.05,
        "volume_ratio_20": 1.0,
    }

    signal = build_signal("601318.SH", features, _BASE_CONFIG)

    assert signal["action"] == "HOLD"


def test_compute_technical_score_weights():
    features = {
        "momentum_20": 1.0,
        "momentum_60": 0.0,
        "ma20_gap": 0.0,
        "ma60_gap": 0.0,
        "volume_ratio_20": 0.0,
        "volatility_20": 0.0,
    }
    score = compute_technical_score(features)
    assert abs(score - 0.30) < 1e-9
