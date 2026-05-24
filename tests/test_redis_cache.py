from src.storage.redis_cache import should_use_redis_cache


def test_redis_cache_disabled_by_default():
    assert should_use_redis_cache(redis_enabled=False, redis_role="none") is False


def test_redis_cache_requires_explicit_runtime_role():
    assert should_use_redis_cache(redis_enabled=True, redis_role="cache") is True