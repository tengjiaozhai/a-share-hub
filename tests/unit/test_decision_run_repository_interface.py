import pytest
from abc import ABC
from src.domain.interfaces.decision_run_repository import DecisionRunRepository


def test_decision_run_repository_is_abstract():
    """验证DecisionRunRepository是抽象类"""
    assert issubclass(DecisionRunRepository, ABC)
    
    # 不能直接实例化抽象类
    with pytest.raises(TypeError):
        DecisionRunRepository()


def test_decision_run_repository_has_required_methods():
    """验证接口有所有必需的方法"""
    required_methods = [
        'insert_decision_run',
        'get_decision_run', 
        'list_decision_runs',
        'delete_decision_run'
    ]
    
    for method in required_methods:
        assert hasattr(DecisionRunRepository, method)
        assert callable(getattr(DecisionRunRepository, method))