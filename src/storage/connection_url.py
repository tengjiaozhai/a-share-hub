"""Canonical DATABASE_URL parsing and psycopg DSN conversion.

Every PostgreSQL consumer in the codebase must use these helpers instead of
hand-building connection strings.  This ensures that switching to a tunnelled
loopback address only requires changing ``DATABASE_URL`` in one place.
"""

from __future__ import annotations

from sqlalchemy.engine import make_url


def build_psycopg_dsn(database_url: str) -> str:
    """Convert a SQLAlchemy-style URL (``postgresql+psycopg://…``) into a plain
    psycopg DSN (``postgresql://…``).

    Raises ``ValueError`` when *database_url* is empty or ``None``.
    """
    if not database_url:
        raise ValueError("DATABASE_URL is empty")
    url = make_url(database_url)
    drivername = url.drivername.split("+", 1)[0]
    return url.set(drivername=drivername).render_as_string(hide_password=False)


def extract_local_runtime_host_port(database_url: str) -> tuple[str, int]:
    """Return ``(host, port)`` after verifying the URL targets a loopback
    address (``127.0.0.1`` or ``localhost``).

    In real runtime the tunnel exposes the AWS PostgreSQL on a local port, so
    any non-loopback host is a misconfiguration and must fail fast.
    """
    if not database_url:
        raise ValueError("DATABASE_URL is empty")
    url = make_url(database_url)
    host = url.host or ""
    port = int(url.port or 5432)
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError(f"runtime DATABASE_URL must use loopback host, got: {host!r}")
    return host, port
