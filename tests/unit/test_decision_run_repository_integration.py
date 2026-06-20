import pytest
from fastapi.testclient import TestClient
from tests.unit.repositories.in_memory_decision_run_repository import InMemoryDecisionRunRepository
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'a-share-hub'))

TEST_USER_ID = "test-user"


@pytest.fixture
def repository():
    return InMemoryDecisionRunRepository()


@pytest.fixture
def client(repository):
    from src.main import build_app
    from src.storage.dependencies import get_decision_run_repository
    from src.api.dependencies import get_current_user, get_current_user_id

    app = build_app()
    app.dependency_overrides[get_decision_run_repository] = lambda: repository
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": TEST_USER_ID,
        "username": "test-user",
        "email": "test@example.com",
        "role": "user",
    }
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID

    return TestClient(app)


def test_list_decision_runs_empty(client):
    """测试空列表"""
    response = client.get("/api/v1/decision-runs")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_decision_runs(client, repository):
    """测试创建和列出决策运行记录"""
    # 先插入一条记录
    repository.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="abc123",
        model_name="deepseek",
        raw_output='{"action": "BUY"}',
        parsed_action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        input_snapshot={},
    )

    # 查询列表
    response = client.get("/api/v1/decision-runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "600519.SH"


def test_get_decision_run(client, repository):
    """测试获取单个决策运行记录"""
    # 先插入一条记录
    decision_run_id = repository.insert_decision_run(
        user_id=TEST_USER_ID,
        symbol="600519.SH",
        prompt_hash="abc123",
        model_name="deepseek",
        raw_output='{"action": "BUY"}',
        parsed_action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        input_snapshot={},
    )

    # 查询单条记录
    response = client.get(f"/api/v1/decision-runs/{decision_run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "600519.SH"
    assert data["decision_run_id"] == decision_run_id


def test_get_nonexistent_decision_run(client):
    """测试获取不存在的决策运行记录"""
    response = client.get("/api/v1/decision-runs/nonexistent")
    assert response.status_code == 404
