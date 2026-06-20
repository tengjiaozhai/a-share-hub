import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

# 测试期间让 auth_security 内部直接调用的 get_runtime_store() 也能连上 SQLite
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DB_POOL_SIZE", "0")
os.environ.setdefault("DB_MAX_OVERFLOW", "0")
os.environ.setdefault("DB_POOL_TIMEOUT_SECONDS", "0")

from src.api.dependencies import get_current_user_id
from src.core.tenant import SYSTEM_TENANT
from src.main import build_app, build_cli_parser
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.api.dependencies import get_user_runtime_store
from src.storage.dependencies import (
    get_decision_run_repository,
    get_settings,
)
from src.storage.auth_models import AppUserRow
from src.api.auth_security import hash_password
from src.infrastructure.repositories.sqlalchemy_decision_run_repository import (
    SQLAlchemyDecisionRunRepository,
)

# 清缓存让 env 生效
get_settings.cache_clear()
import src.storage.dependencies as _deps
_deps._runtime_store_instance = None
_deps._decision_run_repo_instance = None

TEST_USER_ID = "test-user"


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    # 预置一个用户（auth_middleware 需要）
    with engine.begin() as conn:
        conn.execute(
            AppUserRow.__table__.insert().values(
                user_id=TEST_USER_ID,
                username="tester",
                email="tester@example.com",
                password_hash=hash_password("TestPass123!"),
                role="user",
                disabled=False,
            )
        )
    return engine


@pytest.fixture
def test_store(test_engine):
    return RuntimeStore(test_engine, SYSTEM_TENANT)


@pytest.fixture
def test_app(test_store):
    app = build_app()
    app.dependency_overrides[get_user_runtime_store] = lambda: test_store
    app.dependency_overrides[get_decision_run_repository] = lambda: SQLAlchemyDecisionRunRepository(test_store.engine)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return app


def _wire_test_store(test_store):
    """把 test_store 接入所有 lru_cached 的单例 + 已被 import 绑定的名字。"""
    import src.storage.dependencies as deps
    from src.api import auth_security
    from src.storage import dependencies as dep_mod

    deps._decision_run_repo_instance = SQLAlchemyDecisionRunRepository(test_store.engine)
    deps._decision_run_repo_instance = SQLAlchemyDecisionRunRepository(test_store.engine)


def _unwire_test_store():
    """还原 lru_cached 单例。"""
    import src.storage.dependencies as deps
    from src.api import auth_security
    from src.storage import dependencies as dep_mod

    deps._decision_run_repo_instance = None
    # 重新 import 原始函数（带 lru_cache 的旧版本）并复位
    import importlib
    # 重新创建最纯净的 get_runtime_store 引用
    from src.storage.dependencies import get_runtime_store as original


def test_cli_exposes_evalution_commands():
    parser = build_cli_parser()
    choices = parser._subparsers._group_actions[0].choices
    assert "decide" in choices
    assert "live-execute" in choices
    assert "halt" in choices
    assert "run-decision" not in choices
    assert "plan-execution" not in choices


def test_cli_exposes_backtest_and_evaluate_shadow_commands():
    parser = build_cli_parser()
    choices = parser._subparsers._group_actions[0].choices

    assert "backtest" in choices
    assert "evaluate-shadow" in choices


def test_decision_runs_route_is_available(test_app, test_store):
    _wire_test_store(test_store)
    try:
        client = TestClient(test_app)
        response = client.get("/api/v1/decision-runs")
        assert response.status_code == 200
    finally:
        _unwire_test_store()


def test_portfolio_targets_route_is_available(test_app, test_store):
    _wire_test_store(test_store)
    try:
        client = TestClient(test_app)
        response = client.get("/api/v1/portfolio-targets/active")
        assert response.status_code == 200
    finally:
        _unwire_test_store()


def test_reconciliation_status_route_is_available(test_app, test_store):
    _wire_test_store(test_store)
    try:
        client = TestClient(test_app)
        response = client.get("/api/v1/reconciliation/status")
        assert response.status_code == 200
    finally:
        _unwire_test_store()
