import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.main import build_app, build_cli_parser
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore
from src.storage.dependencies import get_runtime_store


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_store(test_engine):
    return RuntimeStore(test_engine)


@pytest.fixture
def test_app(test_store):
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: test_store
    return app


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


def test_decision_runs_route_is_available(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/decision-runs")
    assert response.status_code == 200


def test_portfolio_targets_route_is_available(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/portfolio-targets/active")
    assert response.status_code == 200


def test_reconciliation_status_route_is_available(test_app):
    client = TestClient(test_app)
    response = client.get("/api/v1/reconciliation/status")
    assert response.status_code == 200
