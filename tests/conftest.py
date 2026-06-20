import os

# 在导入任何 src.* 模块前设置默认的 SQLite 数据库与池参数
# （避免 auth_security 内部直接调用 get_runtime_engine() 时拿到默认
#  postgresql:// URL + 默认 pool_size=5 组合，导致 SQLite 测试连接失败）
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DB_POOL_SIZE", "0")
os.environ.setdefault("DB_MAX_OVERFLOW", "0")
os.environ.setdefault("DB_POOL_TIMEOUT_SECONDS", "0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api.auth_security import create_auth_token
from src.api.dependencies import get_current_user_id, get_user_runtime_store
from src.core.config import Settings
from src.core.tenant import TenantContext
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from src.main import build_app
from src.storage.dependencies import (
    get_decision_run_repository,
    get_runtime_engine,
    get_settings,
    get_system_runtime_store,
)
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.storage.system_runtime_store import SystemRuntimeStore
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository

get_settings.cache_clear()
get_decision_run_repository.__wrapped__ = None  # type: ignore[attr-defined]
import src.storage.dependencies as _deps  # noqa: E402

_decision_run_repo_instance = None

TEST_USER_ID = "test-user"
TEST_TENANT = TenantContext(TEST_USER_ID)


@pytest.fixture
def pg_engine(tmp_path):
    database_url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/runtime_store.db")
    engine = create_engine(database_url, future=True)
    from src.storage import auth_models  # noqa: F401  (registers app_users on Base.metadata)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def pg_store(pg_engine):
    """包装 pg_engine 为 RuntimeStore，并插入与 auth_token user_id 匹配的测试用户。"""
    from datetime import datetime
    from sqlalchemy import insert
    from src.storage.auth_models import AppUserRow

    store = RuntimeStore(pg_engine, TEST_TENANT)
    try:
        with pg_engine.begin() as conn:
            conn.execute(insert(AppUserRow.__table__).values(
                user_id=TEST_USER_ID,
                username=TEST_USER_ID,
                email=f"{TEST_USER_ID}@test.local",
                password_hash="test-hash-no-login-needed",
                role="admin",
                disabled=False,
                created_at=datetime.utcnow(),
                last_login_at=datetime.utcnow(),
            ))
    except Exception:
        pass  # 已存在
    return store


@pytest.fixture
def in_memory_decision_run_repository():
    return InMemoryDecisionRunRepository()


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def auth_token():
    settings = Settings()
    return create_auth_token(TEST_USER_ID, settings)


@pytest.fixture
def test_app(pg_store, in_memory_decision_run_repository, event_bus, auth_token, monkeypatch):
    import src.api.auth_security as _auth_security
    _original = _auth_security.get_current_user_from_request

    def _patched(request):
        user = getattr(request.state, "user", None)
        if user:
            return user
        settings = Settings()
        token = request.cookies.get(settings.auth_cookie_name)
        if not token:
            return None
        user_id = _auth_security.read_auth_token(token, settings)
        if not user_id:
            return None
        from src.storage.auth_store import AuthStore
        user_row = AuthStore(pg_store.engine).get_user(user_id)
        if not user_row or user_row.get("disabled"):
            return None
        return {
            "user_id": user_row["user_id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "role": user_row["role"],
        }

    monkeypatch.setattr(_auth_security, "get_current_user_from_request", _patched)

    app = build_app()
    app.dependency_overrides[get_user_runtime_store] = lambda: pg_store
    app.dependency_overrides[get_system_runtime_store] = lambda: SystemRuntimeStore(pg_store.engine)
    app.dependency_overrides[get_decision_run_repository] = lambda: in_memory_decision_run_repository
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield app
    monkeypatch.setattr(_auth_security, "get_current_user_from_request", _original)


@pytest.fixture
def authenticated_client(test_app, auth_token):
    settings = Settings()
    client = TestClient(test_app)
    client.cookies.set(settings.auth_cookie_name, auth_token)
    return client


@pytest.fixture
def admin_auth_token():
    settings = Settings()
    return create_auth_token(TEST_USER_ID, settings)


@pytest.fixture
def authenticated_admin_client(test_app, admin_auth_token):
    """认证为管理员用户（test-user 在 pg_store fixture 中是 admin 角色）"""
    settings = Settings()
    client = TestClient(test_app)
    client.cookies.set(settings.auth_cookie_name, admin_auth_token)
    return client


@pytest.fixture
def system_store(pg_store):
    """与 test_app 共享的 SystemRuntimeStore（指向同一 engine）。"""
    return SystemRuntimeStore(pg_store.engine)