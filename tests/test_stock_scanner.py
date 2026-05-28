import pandas as pd

from src.strategy.stock_scanner import score_quote, scan_market


def test_score_quote_returns_buy_for_strong_stock():
    result = score_quote({
        "symbol": "300750.SZ", "name": "宁德时代",
        "change_pct": 6.0, "amplitude": 10.0, "turnover": 8.0, "volume_ratio": 3.5,
    })
    assert result["action"] == "BUY"
    assert result["score"] >= 0.55
    assert result["reason"]
    assert "symbol" in result
    assert "factors" in result


def test_score_quote_returns_sell_for_declining_stock():
    result = score_quote({
        "symbol": "000001.SZ", "name": "平安银行",
        "change_pct": -4.76, "amplitude": 8.0, "turnover": 1.0, "volume_ratio": 0.5,
    })
    assert result["action"] == "SELL"


def test_score_quote_returns_hold_for_neutral_stock():
    result = score_quote({
        "symbol": "600519.SH", "name": "贵州茅台",
        "change_pct": 0.5, "amplitude": 3.0, "turnover": 1.0, "volume_ratio": 1.2,
    })
    assert result["action"] == "HOLD"


def test_score_quote_handles_missing_fields():
    result = score_quote({"symbol": "600519.SH"})
    assert result["action"] == "SELL"  # change_pct=0 < -3 threshold not met, but score=0 <= 0.20


def test_scan_market_returns_grouped_results():
    mock_quotes = pd.DataFrame([
        {"symbol": "300750.SZ", "name": "宁德时代",
         "change_pct": 6.0, "amplitude": 10.0, "turnover": 8.0, "volume_ratio": 3.5},
        {"symbol": "600519.SH", "name": "贵州茅台",
         "change_pct": 0.5, "amplitude": 3.0, "turnover": 1.0, "volume_ratio": 1.2},
        {"symbol": "000001.SZ", "name": "平安银行",
         "change_pct": -4.76, "amplitude": 8.0, "turnover": 1.0, "volume_ratio": 0.5},
    ])

    result = scan_market(
        [{"symbol": "300750.SZ"}, {"symbol": "600519.SH"}, {"symbol": "000001.SZ"}],
        lambda syms: mock_quotes,
    )

    assert result["total_scanned"] == 3
    assert len(result["buy"]) == 1
    assert result["buy"][0]["symbol"] == "300750.SZ"
    assert len(result["sell"]) == 1
    assert result["sell"][0]["symbol"] == "000001.SZ"
    assert len(result["hold"]) == 1


def test_scan_market_respects_top_n():
    mock_quotes = pd.DataFrame([
        {"symbol": f"00000{i}.SZ", "name": f"股票{i}",
         "change_pct": 6.0, "amplitude": 10.0, "turnover": 8.0, "volume_ratio": 3.5}
        for i in range(20)
    ])

    result = scan_market(
        [{"symbol": f"00000{i}.SZ"} for i in range(20)],
        lambda syms: mock_quotes,
        top_n=5,
    )

    assert len(result["buy"]) == 5


def test_scan_market_handles_empty_quotes():
    result = scan_market(
        [{"symbol": "600519.SH"}],
        lambda syms: pd.DataFrame(),
    )
    assert result["total_scanned"] == 0
    assert result["buy"] == []
