from functools import lru_cache

from src.core.config import Settings
from src.storage.db import create_runtime_engine, ensure_runtime_schema
from src.storage.runtime_store import RuntimeStore
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import SQLAlchemyDecisionRunRepository


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_runtime_store() -> RuntimeStore:
    settings = get_settings()
    engine = create_runtime_engine(settings)
    ensure_runtime_schema(engine)
    return RuntimeStore(engine)


@lru_cache(maxsize=1)
def get_decision_run_repository() -> DecisionRunRepository:
    """获取决策运行记录Repository实例"""
    settings = get_settings()
    engine = create_runtime_engine(settings)
    return SQLAlchemyDecisionRunRepository(engine)
