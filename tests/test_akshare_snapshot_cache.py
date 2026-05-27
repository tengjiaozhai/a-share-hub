from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache


def test_snapshot_cache_returns_matching_row_without_refetch():
    calls = {"count": 0}

    def fetcher():
        calls["count"] += 1
        return pd.DataFrame(
            [
                {"代码": "000858", "名称": "五 粮 液", "最新价": 128.52, "今开": 127.80, "最高": 129.00, "最低": 127.10, "成交量": 123456, "成交额": 987654321.0},
            ]
        )

    cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=3, open_seconds=30)

    first = cache.get_row("000858", fetcher, code_col="代码")
    second = cache.get_row("000858", fetcher, code_col="代码")

    assert first["代码"] == "000858"
    assert second["代码"] == "000858"
    assert calls["count"] == 1


def test_snapshot_cache_opens_breaker_after_repeated_failures():
    calls = {"count": 0}

    def fetcher():
        calls["count"] += 1
        raise RuntimeError("upstream reset")

    cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=2, open_seconds=60)

    with pytest.raises(AkshareUpstreamError):
        cache.get_row("000858", fetcher)
    with pytest.raises(AkshareUpstreamError):
        cache.get_row("000858", fetcher)
    with pytest.raises(AkshareBreakerOpenError):
        cache.get_row("000858", fetcher)

    assert calls["count"] == 2
