import pytest
from datetime import datetime, timezone
from src.domain.events.base import DomainEvent, EventMetadata


class TestEvent(DomainEvent):
    """测试用事件"""
    
    def __init__(self, data: str):
        super().__init__()
        object.__setattr__(self, 'data', data)
    
    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self.data,
        }


def test_create_domain_event():
    """测试创建领域事件"""
    event = TestEvent("test_data")
    
    assert event.event_id is not None
    assert event.event_id.startswith("evt-")
    assert event.event_type == "TestEvent"
    assert event.occurred_at is not None
    assert event.data == "test_data"


def test_event_immutability():
    """测试事件不可变性"""
    event = TestEvent("test_data")
    
    with pytest.raises(AttributeError):
        event.event_id = "new_id"
    
    with pytest.raises(AttributeError):
        event.occurred_at = datetime.now(timezone.utc)


def test_event_to_dict():
    """测试事件转换为字典"""
    event = TestEvent("test_data")
    event_dict = event.to_dict()
    
    assert event_dict["event_id"] == event.event_id
    assert event_dict["event_type"] == "TestEvent"
    assert event_dict["data"] == "test_data"
    assert "occurred_at" in event_dict


def test_event_str():
    """测试事件字符串表示"""
    event = TestEvent("test_data")
    event_str = str(event)
    
    assert "TestEvent" in event_str
    assert event.event_id in event_str


def test_create_event_metadata():
    """测试创建事件元数据"""
    metadata = EventMetadata(
        correlation_id="corr-123",
        causation_id="cause-456",
        user_id="user-789",
        source="test_source",
    )
    
    assert metadata.correlation_id == "corr-123"
    assert metadata.causation_id == "cause-456"
    assert metadata.user_id == "user-789"
    assert metadata.source == "test_source"


def test_event_metadata_to_dict():
    """测试事件元数据转换为字典"""
    metadata = EventMetadata(
        correlation_id="corr-123",
        causation_id="cause-456",
        user_id="user-789",
        source="test_source",
    )
    
    metadata_dict = metadata.to_dict()
    
    assert metadata_dict["correlation_id"] == "corr-123"
    assert metadata_dict["causation_id"] == "cause-456"
    assert metadata_dict["user_id"] == "user-789"
    assert metadata_dict["source"] == "test_source"
