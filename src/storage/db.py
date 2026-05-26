from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings
from src.storage.models import Base

_runtime_schema_bootstrap_lock = Lock()


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
    if not Base.metadata.tables:
        return

    with _runtime_schema_bootstrap_lock:
        Base.metadata.create_all(engine)


def create_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
