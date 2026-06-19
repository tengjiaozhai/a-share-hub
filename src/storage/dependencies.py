from functools import lru_cache

from src.core.config import Settings
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import SQLAlchemyDecisionRunRepository
from src.storage.db import create_runtime_engine, ensure_runtime_schema
from src.storage.runtime_store import RuntimeStore


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


_runtime_store_instance: RuntimeStore | None = None


def get_runtime_store() -> RuntimeStore:
    """获取 RuntimeStore 单例（支持测试覆盖：直接赋值 _runtime_store_instance 即可）。"""
    global _runtime_store_instance
    if _runtime_store_instance is not None:
        return _runtime_store_instance
    settings = get_settings()
    engine = create_runtime_engine(settings)
    ensure_runtime_schema(engine)
    _runtime_store_instance = RuntimeStore(engine)
    return _runtime_store_instance


_decision_run_repo_instance: DecisionRunRepository | None = None


def get_decision_run_repository() -> DecisionRunRepository:
    """获取决策运行记录Repository实例（支持测试覆盖：直接赋值 _decision_run_repo_instance）。"""
    global _decision_run_repo_instance
    if _decision_run_repo_instance is not None:
        return _decision_run_repo_instance
    settings = get_settings()
    engine = create_runtime_engine(settings)
    _decision_run_repo_instance = SQLAlchemyDecisionRunRepository(engine)
    return _decision_run_repo_instance
