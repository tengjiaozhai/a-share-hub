from src.decision.input_builder import build_decision_input_snapshot

def test_decision_input_snapshot_contains_market_and_feature_context():
    snapshot = build_decision_input_snapshot(
        symbol="600519.SH",
        features={"rsi": 52.0, "ma20_gap": 0.06},
        market_context={"session": "AM", "index_change": 0.4},
    )
    assert snapshot["symbol"] == "600519.SH"
    assert snapshot["features"]["rsi"] == 52.0
    assert snapshot["market_context"]["session"] == "AM"

def test_decision_input_snapshot_structure():
    snapshot = build_decision_input_snapshot(
        symbol="300750.SZ",
        features={},
        market_context={},
    )
    assert "symbol" in snapshot
    assert "features" in snapshot
    assert "market_context" in snapshot
