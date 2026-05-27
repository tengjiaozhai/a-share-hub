from src.indicators.technical_indicators import compute_feature_row

def test_compute_feature_row_with_sufficient_data():
    prices = [100.0 + i for i in range(65)]
    features = compute_feature_row(prices)
    assert "ma20_gap" in features
    assert "rsi_14" in features
    assert 0 <= features["rsi_14"] <= 100

def test_compute_feature_row_with_insufficient_data():
    prices = [100.0, 101.0, 102.0]
    features = compute_feature_row(prices)
    assert features["ma20_gap"] == 0.0
    assert features["rsi_14"] == 50.0