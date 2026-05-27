from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import pandas as pd

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError


class SpotSnapshotCache:
    def __init__(self, ttl_seconds: int = 10, failure_threshold: int = 3, open_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._frame: pd.DataFrame | None = None
        self._expires_at: datetime | None = None
        self._failures = 0
        self._breaker_until: datetime | None = None

    def get_row(self, code: str, fetcher: Callable[[], pd.DataFrame], code_col: str = "code") -> pd.Series:
        frame = self._get_frame(fetcher)
        row = frame[frame[code_col] == code]
        if row.empty:
            raise KeyError(code)
        return row.iloc[0]

    def _get_frame(self, fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        now = datetime.utcnow()
        if self._breaker_until is not None and now < self._breaker_until:
            raise AkshareBreakerOpenError("akshare spot snapshot breaker is open")
        if self._frame is not None and self._expires_at is not None and now < self._expires_at:
            return self._frame
        try:
            frame = fetcher()
        except Exception as exc:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._breaker_until = now + timedelta(seconds=self.open_seconds)
            raise AkshareUpstreamError(str(exc)) from exc
        self._frame = frame
        self._expires_at = now + timedelta(seconds=self.ttl_seconds)
        self._failures = 0
        self._breaker_until = None
        return frame
