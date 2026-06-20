"""清理 PostgreSQL 僵尸 idle-in-transaction 连接。

当应用进程被 `pkill -9` 杀死时，部分连接可能残留在 idle-in-transaction 状态
并持有表锁，阻塞 DDL。本脚本主动终止这些连接。

用法：
    python scripts/db_cleanup_zombies.py [--dry-run] [--min-idle-seconds 60]

建议加入 cron：
    */5 * * * * cd /home/ec2-user/a-share-hub && /opt/anaconda3/envs/py311/bin/python scripts/db_cleanup_zombies.py --min-idle-seconds 60 >> /var/log/db_cleanup.log 2>&1
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from src.core.config import Settings  # noqa: E402


def find_zombie_connections(conn, min_idle_seconds: int) -> list[tuple[int, str, str, str]]:
    """查找 idle-in-transaction 且状态时长超过阈值的连接。"""
    threshold = datetime.now(timezone.utc) - timedelta(seconds=min_idle_seconds)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pid, state, query_start, LEFT(query, 80) AS query_preview
            FROM pg_stat_activity
            WHERE state = 'idle in transaction'
              AND query_start < %s
              AND pid != pg_backend_pid()
              AND application_name = 'a-share-hub'
            ORDER BY query_start
            """,
            (threshold,),
        )
        return [(r[0], r[1], r[2].isoformat() if r[2] else "", r[3]) for r in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 PostgreSQL 僵尸 idle-in-tx 连接")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不实际终止")
    parser.add_argument(
        "--min-idle-seconds", type=int, default=60, help="最小空闲秒数（默认 60）"
    )
    args = parser.parse_args()

    settings = Settings()
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg.connect(dsn, autocommit=False)
    try:
        zombies = find_zombie_connections(conn, args.min_idle_seconds)
        if not zombies:
            print(f"[{datetime.now().isoformat()}] no zombie connections (threshold={args.min_idle_seconds}s)")
            return 0

        print(f"[{datetime.now().isoformat()}] found {len(zombies)} zombie connections:")
        for pid, state, started, query in zombies:
            print(f"  pid={pid} state={state} started={started} query={query!r}")

        if args.dry_run:
            print("--dry-run set; not terminating")
            return 0

        terminated = []
        for pid, *_ in zombies:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
                    terminated.append((pid, cur.fetchone()[0]))
            except Exception as exc:
                terminated.append((pid, f"error: {exc}"))
        conn.commit()

        print(f"terminated {sum(1 for _, ok in terminated if ok)}/{len(zombies)} connections")
        for pid, ok in terminated:
            print(f"  pid={pid} -> {ok}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
