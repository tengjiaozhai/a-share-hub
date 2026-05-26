import os

import pytest
from sqlalchemy import create_engine

from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


@pytest.fixture
def pg_engine():
    database_url = os.environ["TEST_DATABASE_URL"]
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
def test_app(pg_store):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: pg_store
    return app
