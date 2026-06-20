from threading import Lock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings
from src.storage.models import Base

_runtime_schema_bootstrap_lock = Lock()


def create_runtime_engine(settings: Settings):
    """构造 SQLAlchemy 引擎。

    防御层 2：客户端连接池回收 + 单连接超时，防止僵尸连接持锁阻塞 DDL。
    """
    engine_kwargs = dict(
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,           # 30 分钟回收，避免长时间空闲被服务端超时
        pool_reset_on_return="rollback",  # 连接归还时回滚未提交事务，防止 idle-in-tx
        echo=settings.db_echo,
    )
    # SQLite 的 SingletonThreadPool / NullPool 不接受 QueuePool 专属参数。
    # 仅在显式配置 pool_size > 0 时才传递 pool 调优参数。
    if settings.db_pool_size and settings.db_pool_size > 0:
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
        engine_kwargs["pool_timeout"] = settings.db_pool_timeout_seconds

    # PG 专属：客户端级 idle-in-tx 超时（与 DB SET 互为冗余保护）
    connect_args: dict = {}
    if settings.database_url.startswith(("postgresql", "postgres")):
        connect_args["options"] = "-c idle_in_transaction_session_timeout=300 -c statement_timeout=600000 -c lock_timeout=120000"
        connect_args["connect_timeout"] = 10
    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    engine = create_engine(settings.database_url, **engine_kwargs)

    # 监听：在新连接上设置 search_path 和 statement_timeout（防御层 2 补充）
    _dialect_name = engine.dialect.name
    @event.listens_for(engine, "connect")
    def _set_session_settings(dbapi_connection, connection_record):  # noqa: ANN001
        # SQLite 不支持 PG 专用 SET 语句；测试用 sqlite3.Cursor 也不支持 context manager
        if _dialect_name == "sqlite":
            return
        try:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("SET application_name = 'a-share-hub'")
                cursor.execute("SET idle_in_transaction_session_timeout = '5min'")
                cursor.execute("SET statement_timeout = '10min'")
                cursor.execute("SET lock_timeout = '2min'")
            finally:
                cursor.close()
            dbapi_connection.commit()
        except Exception:
            pass

    return engine


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
