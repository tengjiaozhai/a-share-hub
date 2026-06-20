from functools import lru_cache

from src.core.config import Settings
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import SQLAlchemyDecisionRunRepository
from src.storage.db import create_runtime_engine, ensure_runtime_schema
from src.storage.system_runtime_store import SystemRuntimeStore


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


_runtime_engine = None


def get_runtime_engine():
    """获取运行时数据库引擎（单例）。"""
    global _runtime_engine
    if _runtime_engine is None:
        settings = get_settings()
        _runtime_engine = create_runtime_engine(settings)
        ensure_runtime_schema(_runtime_engine)
    return _runtime_engine


def get_system_runtime_store() -> SystemRuntimeStore:
    """获取 SystemRuntimeStore（全局 Kill Switch / broker owner 解析）。"""
    return SystemRuntimeStore(get_runtime_engine())


# Task 4 边界：未授权的 RuntimeStore 单例已删除。
# 调用方必须通过 API 层 get_user_runtime_store(tenant) 显式绑定 TenantContext。

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