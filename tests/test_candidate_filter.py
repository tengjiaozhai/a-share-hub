from src.strategy.candidate_filter import rank_candidates, filter_by_volume

def test_rank_candidates_keeps_top_symbols_only():
    rows = [
        {"symbol": "600519.SH", "technical_score": 88},
        {"symbol": "300750.SZ", "technical_score": 82},
        {"symbol": "000001.SZ", "technical_score": 61},
    ]
    ranked = rank_candidates(rows, top_n=2)
    assert [row["symbol"] for row in ranked] == ["600519.SH", "300750.SZ"]

def test_filter_by_volume():
    rows = [
        {"symbol": "600519.SH", "volume": 50000},
        {"symbol": "300750.SZ", "volume": 5000},
    ]
    filtered = filter_by_volume(rows, min_volume=10000)
    assert len(filtered) == 1
    assert filtered[0]["symbol"] == "600519.SH"