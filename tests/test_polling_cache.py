import threading
import time

from src.api.polling_cache import PollingCache


def test_polling_cache_reuses_fresh_value():
    calls = 0
    cache = PollingCache[int](ttl_seconds=60)

    def refresh() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_refresh("quotes", refresh) == 1
    assert cache.get_or_refresh("quotes", refresh) == 1
    assert calls == 1


def test_polling_cache_returns_stale_value_while_refresh_in_progress():
    cache = PollingCache[int](ttl_seconds=0.01)
    cache.get_or_refresh("quotes", lambda: 1)
    time.sleep(0.02)

    refresh_started = threading.Event()
    release_refresh = threading.Event()

    def slow_refresh() -> int:
        refresh_started.set()
        release_refresh.wait(timeout=1)
        return 2

    thread = threading.Thread(target=lambda: cache.get_or_refresh("quotes", slow_refresh))
    thread.start()
    assert refresh_started.wait(timeout=1)

    assert cache.get_or_refresh("quotes", lambda: 3) == 1

    release_refresh.set()
    thread.join(timeout=1)
    assert cache.get_or_refresh("quotes", lambda: 4) == 2
