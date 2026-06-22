from datetime import date, timedelta

import pytest

from src.alpha.analysis_snapshot import AnalysisSnapshotBuilder


def test_snapshot_uses_weighted_cost_and_computed_features():
    start = date(2026, 3, 1)
    bars = [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "close": 10.0 + index * 0.1,
            "volume": 1000 + index,
        }
        for index in range(61)
    ]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok", "pe_ratio": 18.2},
    )
    snapshot = builder.build(
        symbol="600703.SH",
        lots=[
            {"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
            {"buy_price": 14.0, "quantity": 200, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
        ],
        portfolio_market_value=10_000.0,
    )

    assert snapshot.weighted_avg_cost == pytest.approx(13.333333)
    assert snapshot.close == pytest.approx(16.0)
    assert snapshot.unrealized_pnl == pytest.approx(800.0)
    assert snapshot.technical["bar_count"] == 61
    assert snapshot.technical["ma20"] > snapshot.technical["ma60"]
    assert isinstance(snapshot.technical["reclaimed_ma20"], bool)
    assert snapshot.news == {"status": "unavailable", "items": []}


def test_snapshot_rejects_missing_close():
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: [],
        fundamental_loader=lambda symbol: {"status": "unavailable"},
    )
    with pytest.raises(ValueError, match="no closing price"):
        builder.build(
            symbol="MSFT.US",
            lots=[{"buy_price": 420.0, "quantity": 2.0}],
            portfolio_market_value=840.0,
        )
