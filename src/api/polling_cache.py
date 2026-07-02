from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    expires_at: float
    value: T


class PollingCache(Generic[T]):
    """Small stale-while-refresh cache for dashboard polling endpoints."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, _CacheEntry[T]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def get_or_refresh(self, key: str, refresh: Callable[[], T]) -> T:
        now = time.time()
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value

        lock = self._lock_for(key)
        acquired = lock.acquire(blocking=False)
        if not acquired:
            if entry is not None:
                return entry.value
            with lock:
                refreshed = self._entries.get(key)
                if refreshed is not None:
                    return refreshed.value
                refreshed_value = refresh()
                self._entries[key] = _CacheEntry(
                    expires_at=time.time() + self._ttl_seconds,
                    value=refreshed_value,
                )
                return refreshed_value

        try:
            refreshed_value = refresh()
            self._entries[key] = _CacheEntry(
                expires_at=time.time() + self._ttl_seconds,
                value=refreshed_value,
            )
            return refreshed_value
        except Exception:
            if entry is not None:
                return entry.value
            raise
        finally:
            lock.release()

    def clear(self) -> None:
        with self._guard:
            self._entries.clear()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock
