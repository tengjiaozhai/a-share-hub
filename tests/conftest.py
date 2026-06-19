import os

# 在导入任何 src.* 模块前设置默认的 SQLite 数据库与池参数
# （避免 auth_security 内部直接调用 get_runtime_store() 时拿到默认
#  postgresql:// URL + 默认 pool_size=5 组合，导致 SQLite 测试连接失败）
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DB_POOL_SIZE", "0")
os.environ.setdefault("DB_MAX_OVERFLOW", "0")
os.environ.setdefault("DB_POOL_TIMEOUT_SECONDS", "0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api.auth_security import create_auth_token
from src.api.dependencies import get_current_user_id
from src.core.config import Settings
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from src.main import build_app
from src.storage.dependencies import (
    get_decision_run_repository,
    get_runtime_store,
    get_settings,
)
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository

# 清掉 lru_cache 让测试用的 env（DATABASE_URL/DB_POOL_*）生效
get_settings.cache_clear()
# get_runtime_store / get_decision_run_repository 改为基于全局变量，
# 测试可通过 _runtime_store_instance / _decision_run_repo_instance 覆盖
import src.storage.dependencies as _deps  # noqa: E402

_deps._runtime_store_instance = None
_deps._decision_run_repo_instance = None

TEST_USER_ID = "test-user"


@pytest.fixture
def pg_engine(tmp_path):
    database_url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/runtime_store.db")
    engine = create_engine(database_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def pg_store(pg_engine):
    return RuntimeStore(pg_engine)


@pytest.fixture
def in_memory_decision_run_repository():
    return InMemoryDecisionRunRepository()


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def auth_token():
    """生成一个有效的认证 token。"""
    settings = Settings()
    return create_auth_token(TEST_USER_ID, settings)


@pytest.fixture
def test_app(pg_store, in_memory_decision_run_repository, event_bus, auth_token):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: pg_store
    app.dependency_overrides[get_decision_run_repository] = lambda: in_memory_decision_run_repository
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def authenticated_client(test_app, auth_token):
    """提供已认证的 TestClient。"""
    settings = Settings()
    client = TestClient(test_app)
    client.cookies.set(settings.auth_cookie_name, auth_token)
    return client
