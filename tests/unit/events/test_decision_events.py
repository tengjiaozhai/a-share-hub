import pytest
from datetime import datetime, timezone
from src.domain.events.decision_events import (
    DecisionRunCreated,
    DecisionRunFailed,
    DecisionActionChanged,
)
from src.domain.events.base import EventMetadata


def test_create_decision_run_created_event():
    """测试创建决策运行创建事件"""
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    assert event.event_type == "DecisionRunCreated"
    assert event.decision_run_id == "dr-123"
    assert event.symbol == "600519.SH"
    assert event.action == "BUY"
    assert event.confidence == 0.8
    assert event.target_position_ratio == 0.15
    assert event.reason == "Strong signal"
    assert event.model_name == "deepseek"


def test_decision_run_created_to_dict():
    """测试决策运行创建事件转换为字典"""
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
    )
    
    event_dict = event.to_dict()
    
    assert event_dict["event_id"] == event.event_id
    assert event_dict["event_type"] == "DecisionRunCreated"
    assert event_dict["decision_run_id"] == "dr-123"
    assert event_dict["symbol"] == "600519.SH"
    assert event_dict["action"] == "BUY"
    assert event_dict["confidence"] == 0.8
    assert event_dict["target_position_ratio"] == 0.15
    assert event_dict["reason"] == "Strong signal"
    assert event_dict["model_name"] == "deepseek"


def test_create_decision_run_failed_event():
    """测试创建决策运行失败事件"""
    event = DecisionRunFailed(
        decision_run_id="dr-123",
        symbol="600519.SH",
        error="LLM client returned no output",
        model_name="deepseek",
    )
    
    assert event.event_type == "DecisionRunFailed"
    assert event.decision_run_id == "dr-123"
    assert event.symbol == "600519.SH"
    assert event.error == "LLM client returned no output"
    assert event.model_name == "deepseek"


def test_decision_run_failed_to_dict():
    """测试决策运行失败事件转换为字典"""
    event = DecisionRunFailed(
        decision_run_id="dr-123",
        symbol="600519.SH",
        error="LLM client returned no output",
        model_name="deepseek",
    )
    
    event_dict = event.to_dict()
    
    assert event_dict["event_id"] == event.event_id
    assert event_dict["event_type"] == "DecisionRunFailed"
    assert event_dict["decision_run_id"] == "dr-123"
    assert event_dict["symbol"] == "600519.SH"
    assert event_dict["error"] == "LLM client returned no output"
    assert event_dict["model_name"] == "deepseek"


def test_create_decision_action_changed_event():
    """测试创建决策动作变更事件"""
    event = DecisionActionChanged(
        decision_run_id="dr-123",
        symbol="600519.SH",
        old_action="HOLD",
        new_action="BUY",
        reason="Strong signal",
    )
    
    assert event.event_type == "DecisionActionChanged"
    assert event.decision_run_id == "dr-123"
    assert event.symbol == "600519.SH"
    assert event.old_action == "HOLD"
    assert event.new_action == "BUY"
    assert event.reason == "Strong signal"


def test_decision_action_changed_to_dict():
    """测试决策动作变更事件转换为字典"""
    event = DecisionActionChanged(
        decision_run_id="dr-123",
        symbol="600519.SH",
        old_action="HOLD",
        new_action="BUY",
        reason="Strong signal",
    )
    
    event_dict = event.to_dict()
    
    assert event_dict["event_id"] == event.event_id
    assert event_dict["event_type"] == "DecisionActionChanged"
    assert event_dict["decision_run_id"] == "dr-123"
    assert event_dict["symbol"] == "600519.SH"
    assert event_dict["old_action"] == "HOLD"
    assert event_dict["new_action"] == "BUY"
    assert event_dict["reason"] == "Strong signal"


def test_decision_event_with_metadata():
    """测试带元数据的决策事件"""
    metadata = EventMetadata(
        correlation_id="corr-123",
        causation_id="cause-456",
        user_id="user-789",
        source="test_source",
    )
    
    event = DecisionRunCreated(
        decision_run_id="dr-123",
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        target_position_ratio=0.15,
        reason="Strong signal",
        model_name="deepseek",
        metadata=metadata,
    )
    
    event_dict = event.to_dict()
    
    assert "metadata" in event_dict
    assert event_dict["metadata"]["correlation_id"] == "corr-123"
    assert event_dict["metadata"]["causation_id"] == "cause-456"
    assert event_dict["metadata"]["user_id"] == "user-789"
    assert event_dict["metadata"]["source"] == "test_source"
