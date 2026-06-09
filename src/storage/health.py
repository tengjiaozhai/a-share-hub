"""Runtime database health probe.

Used by readiness endpoints, CLI scripts, and systemd ``ExecStartPre`` to
confirm that the SSH tunnel (or direct connection) is alive and the database
is accepting queries.
"""

from __future__ import annotations

from time import perf_counter

from sqlalchemy import text


def probe_runtime_database(engine) -> dict:
    """Execute ``SELECT 1`` against *engine* and report success / latency.

    Returns a dict with at least ``{"ok": bool, "latency_ms": float}``.
    On failure the dict also contains ``"error"`` with the exception text.
    """
    started = perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


def probe_runtime_database_from_settings() -> dict:
    """Convenience wrapper that builds an engine from ``Settings()`` and
    probes it.  Suitable for CLI scripts and simple readiness checks.
    """
    from src.core.config import Settings
    from src.storage.db import create_runtime_engine

    engine = create_runtime_engine(Settings())
    return probe_runtime_database(engine)
