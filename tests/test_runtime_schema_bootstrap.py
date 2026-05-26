from sqlalchemy import create_engine, inspect, text
from concurrent.futures import ThreadPoolExecutor

from src.storage.db import ensure_runtime_schema
from src.storage.models import Base


def test_ensure_runtime_schema_creates_tables_for_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/empty.db", future=True)

    ensure_runtime_schema(engine)

    table_names = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables.keys()).issubset(table_names)


def test_ensure_runtime_schema_creates_missing_tables_when_only_alembic_version_exists(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/partial.db", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))

    ensure_runtime_schema(engine)

    table_names = set(inspect(engine).get_table_names())
    assert "alembic_version" in table_names
    assert set(Base.metadata.tables.keys()).issubset(table_names)


def test_ensure_runtime_schema_is_safe_under_concurrent_calls(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/concurrent.db", future=True)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: ensure_runtime_schema(engine), range(8)))

    assert results == [None] * 8
    table_names = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables.keys()).issubset(table_names)
