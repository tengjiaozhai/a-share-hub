import threading
import time
from typing import Any


class TTLMemoryCache:
    """基于 TTL 的内存缓存，线程安全。"""

    def __init__(self, ttl_seconds: int = 60, maxsize: int = 1024):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize:
                self._evict_expired()
            if len(self._store) >= self._maxsize:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = (time.time() + self._ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
