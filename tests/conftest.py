import os

import pytest
from sqlalchemy import create_engine

from src.main import build_app
from src.storage.dependencies import get_runtime_store, get_decision_run_repository
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository


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
def test_app(pg_store, in_memory_decision_run_repository, event_bus):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: pg_store
    app.dependency_overrides[get_decision_run_repository] = lambda: in_memory_decision_run_repository
    # 注意：这里需要添加事件总线的依赖注入
    return app
