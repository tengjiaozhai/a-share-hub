from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings
from src.storage.models import Base


def create_runtime_engine(settings: Settings):
    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        echo=settings.db_echo,
    )


def ensure_runtime_schema(engine) -> None:
    required_tables = set(Base.metadata.tables.keys())
    if not required_tables:
        return

    existing_tables = set(inspect(engine).get_table_names())
    if not existing_tables:
        Base.metadata.create_all(engine)
        return

    missing_tables = required_tables - existing_tables
    if missing_tables:
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in sorted(missing_tables)])


def create_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
