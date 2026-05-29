import pandas as pd
import pytest

from src.strategy.stock_scanner import score_quote, scan_market, confirm_buy_candidates


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
    assert result["action"] == "SELL"
    assert result["score"] >= 0


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


def test_confirm_buy_candidates_filters_holds(monkeypatch):
    from src.strategy.strategy_config import StrategyConfig

    config = StrategyConfig(top_n=10, max_position_ratio=0.2, buy_score_threshold=0.55, sell_score_threshold=-0.20)

    candidates = [
        {"symbol": "300750.SZ", "name": "宁德时代", "score": 0.68, "action": "BUY", "reason": "涨幅6%"},
        {"symbol": "000001.SZ", "name": "平安银行", "score": 0.60, "action": "BUY", "reason": "涨幅3%"},
    ]

    call_count = {"n": 0}

    def mock_build_signal(symbol, features, config):
        call_count["n"] += 1
        if symbol == "300750.SZ":
            return {"symbol": symbol, "action": "BUY", "technical_score": 0.62}
        return {"symbol": symbol, "action": "HOLD", "technical_score": 0.10}

    monkeypatch.setattr("src.strategy.signal_engine.build_signal", mock_build_signal)

    def mock_kline_fn(symbol, start, end):
        return pd.DataFrame({
            "date": [f"2025-01-{i+1:02d}" for i in range(60)],
            "close": [100 + i for i in range(60)],
        })

    result = confirm_buy_candidates(candidates, mock_kline_fn, config)

    assert call_count["n"] == 2
    assert len(result) == 2
    # 300750 confirmed, 000001 not confirmed; confirmed sorted first
    assert result[0]["symbol"] == "300750.SZ"
    assert result[0]["confirmed"] is True
    assert result[0]["final_action"] == "BUY"
    assert result[1]["symbol"] == "000001.SZ"
    assert result[1]["confirmed"] is False
    assert result[1]["final_action"] == "HOLD"


def test_confirm_buy_candidates_marks_insufficient_data():
    from src.strategy.strategy_config import StrategyConfig

    config = StrategyConfig(top_n=10, max_position_ratio=0.2, buy_score_threshold=0.55, sell_score_threshold=-0.20)

    candidates = [
        {"symbol": "NEW.SZ", "name": "新股", "score": 0.70, "action": "BUY", "reason": "涨幅8%"},
    ]

    def mock_kline_fn(symbol, start, end):
        return pd.DataFrame({"date": ["2025-01-01"], "close": [50]})

    result = confirm_buy_candidates(candidates, mock_kline_fn, config)

    assert len(result) == 1
    assert result[0]["confirmed"] is False
    assert "历史数据不足" in result[0]["confirm_reason"]
