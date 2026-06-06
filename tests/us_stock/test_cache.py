import time

from src.us_stock.cache import TTLMemoryCache


def test_get_miss_returns_none():
    cache = TTLMemoryCache(ttl_seconds=1)
    assert cache.get("missing") is None


def test_set_and_get_hit():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("key1", {"value": 42})
    assert cache.get("key1") == {"value": 42}


def test_expired_entry_returns_none():
    cache = TTLMemoryCache(ttl_seconds=1)
    cache.set("key1", "data")
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_delete():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("key1", "data")
    cache.delete("key1")
    assert cache.get("key1") is None


def test_clear():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
