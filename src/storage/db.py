from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings
from src.storage.models import Base

_runtime_schema_bootstrap_lock = Lock()


def create_runtime_engine(settings: Settings):
    engine_kwargs = dict(
        future=True,
        pool_pre_ping=True,
        echo=settings.db_echo,
    )
    # SQLite 的 SingletonThreadPool / NullPool 不接受 QueuePool 专属参数。
    # 仅在显式配置 pool_size > 0 时才传递 pool 调优参数。
    if settings.db_pool_size and settings.db_pool_size > 0:
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
        engine_kwargs["pool_timeout"] = settings.db_pool_timeout_seconds
    return create_engine(settings.database_url, **engine_kwargs)


def ensure_runtime_schema(engine) -> None:
    if not Base.metadata.tables:
        return

    with _runtime_schema_bootstrap_lock:
        from src.storage import auth_models  # noqa: F401

        Base.metadata.create_all(engine)

        try:
            from src.paper_ledger.models import PaperBase
            if PaperBase.metadata.tables:
                PaperBase.metadata.create_all(engine)
        except Exception:
            pass


def create_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
