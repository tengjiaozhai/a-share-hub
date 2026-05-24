from src.storage.redis_cache import evaluate_redis_enablement


def test_redis_not_required_for_low_load_shadow_run():
    result = evaluate_redis_enablement(
        cpu_p95=35.0,
        memory_p95=48.0,
        api_latency_p95_ms=90.0,
        mem_available_mb=1200,
        disk_free_mb=3600,
        ready_plan_reads_per_second=2.0,
        broker_events_per_second=3.0,
        workers=1,
    )
    assert result["enable_redis"] is False
    assert "insufficient host reserve" in result["reasons"]


def test_redis_recommended_for_hot_read_or_multi_worker_load():
    result = evaluate_redis_enablement(
        cpu_p95=72.0,
        memory_p95=70.0,
        api_latency_p95_ms=260.0,
        mem_available_mb=1900,
        disk_free_mb=3600,
        ready_plan_reads_per_second=45.0,
        broker_events_per_second=25.0,
        workers=3,
    )
    assert result["enable_redis"] is True
    assert "multi-worker hot read load" in result["reasons"]