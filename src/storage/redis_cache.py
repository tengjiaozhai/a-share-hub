import json

from redis import Redis


def should_use_redis_cache(redis_enabled: bool, redis_role: str) -> bool:
    return redis_enabled and redis_role == "cache"


def evaluate_redis_enablement(
    cpu_p95: float,
    memory_p95: float,
    api_latency_p95_ms: float,
    mem_available_mb: float,
    disk_free_mb: float,
    ready_plan_reads_per_second: float,
    broker_events_per_second: float,
    workers: int,
) -> dict:
    reasons: list[str] = []
    if mem_available_mb < 1536 or disk_free_mb < 3072:
        return {"enable_redis": False, "reasons": ["insufficient host reserve"]}
    if workers > 1 and ready_plan_reads_per_second >= 20.0:
        reasons.append("multi-worker hot read load")
    if api_latency_p95_ms >= 200.0 and ready_plan_reads_per_second >= 15.0:
        reasons.append("control-plane latency under repeated plan polling")
    if cpu_p95 >= 70.0 and memory_p95 >= 65.0:
        reasons.append("server saturation during shadow traffic")
    if broker_events_per_second >= 50.0:
        reasons.append("high broker event burst rate")
    return {"enable_redis": bool(reasons), "reasons": reasons}


class RedisCache:
    def __init__(self, redis_url: str) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.client.set(name=key, value=json.dumps(value, ensure_ascii=True, sort_keys=True), ex=ttl_seconds)

    def get_json(self, key: str) -> dict | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None
