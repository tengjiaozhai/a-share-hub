from sqlalchemy import create_engine

from src.storage.health import probe_runtime_database


def test_probe_reports_ok_for_sqlite():
    engine = create_engine("sqlite:///:memory:", future=True)
    result = probe_runtime_database(engine)
    assert result["ok"] is True
    assert result["latency_ms"] >= 0
    assert "error" not in result


def test_probe_reports_failure_for_bad_engine():
    engine = create_engine("sqlite:///nonexistent/path/db.sqlite", future=True)
    result = probe_runtime_database(engine)
    assert result["ok"] is False
    assert "error" in result
    assert result["latency_ms"] >= 0
