仅当以下所有条件都满足时才启用 Redis：

1. PostgreSQL 支持的影子流量已通过。
2. 已首先验证 `REDIS_ENABLED=false`。
3. 至少一个测量阈值在三个连续观察窗口内被超过：
   - `api_latency_p95_ms >= 200`
   - 当有多个工作者时 `ready_plan_reads_per_second >= 20`
   - `broker_events_per_second >= 50`
   - `cpu_p95 >= 70` 且 `memory_p95 >= 65`
4. 主机在 PostgreSQL 和应用进程后仍保留安全储备：
   - `MemAvailable >= 1536 MiB`
   - `disk free >= 3072 MiB`
   - `REDIS_MAXMEMORY_MB <= 128`
5. Redis 仅用于缓存、基于 TTL 的提示或幂等性加速。
6. PostgreSQL 仍然是执行计划、券商事件和紧急停止开关的真实数据源。