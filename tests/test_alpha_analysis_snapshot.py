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


def test_snapshot_uses_usd_weighted_avg_cost_for_us_symbol():
    bars = [
        {"date": (date(2026, 4, 1) + timedelta(days=index)).isoformat(), "close": 430.0, "volume": 1000}
        for index in range(61)
    ]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
    )

    snapshot = builder.build(
        symbol="MSFT.US",
        lots=[
            {"buy_price": 420.0, "quantity": 2.0, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
            {"buy_price": 430.0, "quantity": 1.0, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20},
        ],
        portfolio_market_value=10_000.0,
    )

    assert snapshot.market == "us"
    assert snapshot.currency == "USD"
    assert snapshot.weighted_avg_cost == pytest.approx(423.333333)
    assert snapshot.unrealized_pnl == pytest.approx((430.0 - 423.3333333333333) * 3.0)


def test_snapshot_uses_news_loader_when_provided():
    start = date(2026, 3, 1)
    bars = [
        {"date": (start + timedelta(days=index)).isoformat(), "close": 10.0 + index * 0.1, "volume": 1000 + index}
        for index in range(61)
    ]
    news_data = {
        "status": "ok",
        "items": [
            {"title": "利好消息", "summary": "公司业绩超预期", "source": "东方财富", "published_at": "2026-06-26", "url": "http://example.com/1"},
            {"title": "行业分析", "summary": "行业景气度提升", "source": "证券时报", "published_at": "2026-06-25", "url": "http://example.com/2"},
        ],
    }
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=lambda symbol: news_data,
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news["status"] == "ok"
    assert len(snapshot.news["items"]) == 2
    assert snapshot.news["items"][0]["title"] == "利好消息"
    assert "news" not in snapshot.data_quality["missing"]


def test_snapshot_gracefully_handles_news_loader_failure():
    start = date(2026, 3, 1)
    bars = [
        {"date": (start + timedelta(days=index)).isoformat(), "close": 10.0 + index * 0.1, "volume": 1000 + index}
        for index in range(61)
    ]

    def failing_loader(symbol):
        raise RuntimeError("network error")

    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=failing_loader,
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news["status"] == "error"
    assert snapshot.news["items"] == []
    assert "news" in snapshot.data_quality["missing"]


def test_snapshot_without_news_loader_behaves_as_before():
    start = date(2026, 3, 1)
    bars = [
        {"date": (start + timedelta(days=index)).isoformat(), "close": 10.0 + index * 0.1, "volume": 1000 + index}
        for index in range(61)
    ]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news == {"status": "unavailable", "items": []}
    assert "news" in snapshot.data_quality["missing"]


def test_snapshot_uses_news_loader_when_provided():
    bars = [
        {"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000}
        for i in range(61)
    ]
    news_data = {
        "status": "ok",
        "items": [
            {"title": "利好消息", "summary": "公司业绩超预期", "source": "东方财富", "published_at": "2026-06-26"},
            {"title": "行业分析", "summary": "行业景气度提升", "source": "证券时报", "published_at": "2026-06-25"},
        ],
    }
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=lambda symbol: news_data,
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news["status"] == "ok"
    assert len(snapshot.news["items"]) == 2
    assert snapshot.news["items"][0]["title"] == "利好消息"
    assert "news" not in snapshot.data_quality["missing"]


def test_snapshot_gracefully_handles_news_loader_failure():
    bars = [
        {"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000}
        for i in range(61)
    ]

    def failing_loader(symbol):
        raise RuntimeError("network error")

    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=failing_loader,
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news["status"] == "error"
    assert snapshot.news["items"] == []
    assert "news" in snapshot.data_quality["missing"]


def test_snapshot_without_news_loader_behaves_as_before():
    bars = [
        {"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000}
        for i in range(61)
    ]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
    )
    snapshot = builder.build(
        symbol="600519",
        lots=[{"buy_price": 12.0, "quantity": 100, "stop_loss_ratio": -0.08, "take_profit_ratio": 0.20}],
        portfolio_market_value=10_000.0,
    )
    assert snapshot.news == {"status": "unavailable", "items": []}
    assert "news" in snapshot.data_quality["missing"]
