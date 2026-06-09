import pytest

from src.storage.connection_url import build_psycopg_dsn, extract_local_runtime_host_port


def test_build_psycopg_dsn_strips_sqlalchemy_driver():
    dsn = build_psycopg_dsn("postgresql+psycopg://user:pass@127.0.0.1:15432/douya")
    assert dsn == "postgresql://user:pass@127.0.0.1:15432/douya"


def test_build_psycopg_dsn_passthrough_plain_postgresql():
    dsn = build_psycopg_dsn("postgresql://user:pass@10.0.0.1:5432/db")
    assert dsn == "postgresql://user:pass@10.0.0.1:5432/db"


def test_build_psycopg_dsn_rejects_empty():
    with pytest.raises(ValueError, match="DATABASE_URL is empty"):
        build_psycopg_dsn("")


def test_extract_local_runtime_host_port_loopback():
    host, port = extract_local_runtime_host_port(
        "postgresql+psycopg://user:pass@127.0.0.1:15432/douya"
    )
    assert host == "127.0.0.1"
    assert port == 15432


def test_extract_local_runtime_host_port_localhost():
    host, port = extract_local_runtime_host_port(
        "postgresql+psycopg://user:pass@localhost:5432/douya"
    )
    assert host == "localhost"
    assert port == 5432


def test_extract_local_runtime_host_port_rejects_remote():
    with pytest.raises(ValueError, match="loopback"):
        extract_local_runtime_host_port(
            "postgresql+psycopg://user:pass@rds.aws.example.com:5432/douya"
        )


def test_extract_local_runtime_host_port_rejects_empty():
    with pytest.raises(ValueError, match="DATABASE_URL is empty"):
        extract_local_runtime_host_port("")
