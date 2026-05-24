"""测试OMS转换的幂等性"""
from src.execution.state_machine import apply_broker_event, create_initial_order_state


def test_duplicate_partial_fill_should_not_increase_filled_quantity():
    """重复的PARTIAL_FILL事件不应该增加filled_quantity"""
    state = create_initial_order_state("O1", "600519.SH", 100, "BUY")
    event = {"event_type": "PARTIAL_FILL", "fill_quantity": 40, "event_id": "evt_001"}
    
    # 第一次应用事件
    state1 = apply_broker_event(state, event)
    assert state1["filled_quantity"] == 40
    assert state1["status"] == "PARTIALLY_FILLED"
    
    # 第二次应用相同事件（模拟重复事件）
    state2 = apply_broker_event(state1, event)
    # 问题：filled_quantity会变成80，但应该保持40
    assert state2["filled_quantity"] == 40, f"重复事件导致filled_quantity从40变为{state2['filled_quantity']}"
    assert state2["status"] == "PARTIALLY_FILLED"


def test_filled_quantity_should_not_exceed_order_quantity():
    """filled_quantity不能超过订单原始数量"""
    state = create_initial_order_state("O2", "600519.SH", 100, "BUY")
    
    # 第一次部分成交
    event1 = {"event_type": "PARTIAL_FILL", "fill_quantity": 60}
    state1 = apply_broker_event(state, event1)
    assert state1["filled_quantity"] == 60
    
    # 第二次部分成交，但fill_quantity会导致超过总量
    event2 = {"event_type": "PARTIAL_FILL", "fill_quantity": 50}
    state2 = apply_broker_event(state1, event2)
    # 问题：filled_quantity会变成110，但应该被限制为100
    assert state2["filled_quantity"] == 100, f"filled_quantity({state2['filled_quantity']})超过订单数量(100)"
    assert state2["status"] == "FILLED"  # 应该自动变为FILLED


def test_detect_status_drift_not_just_quantity():
    """对账需要检测状态漂移，不仅仅是数量漂移"""
    from src.execution.reconciliation import detect_unreconciled_state
    
    # 场景：系统认为订单已成交，但broker显示部分成交
    plan = {"filled_quantity": 100, "status": "FILLED"}
    broker = {"filled_quantity": 100, "status": "PARTIALLY_FILLED"}
    
    # 当前实现只比较数量，会认为没有漂移
    # 应该检测状态不一致
    has_drift = detect_unreconciled_state(plan, broker)
    assert has_drift is True, "应该检测到状态漂移：系统FILLED vs 经纪商PARTIALLY_FILLED"


def test_duplicate_fill_event_with_event_id():
    """测试带event_id的重复事件检测"""
    state = create_initial_order_state("O3", "600519.SH", 100, "BUY")
    event = {
        "event_type": "PARTIAL_FILL",
        "fill_quantity": 40,
        "event_id": "evt_123"  # 添加事件ID用于幂等性检查
    }
    
    # 第一次应用
    state1 = apply_broker_event(state, event)
    assert state1["filled_quantity"] == 40
    
    # 第二次应用相同事件（相同event_id）
    state2 = apply_broker_event(state1, event)
    assert state2["filled_quantity"] == 40, "相同event_id的事件应该被忽略"


if __name__ == "__main__":
    # 运行测试以查看失败
    import pytest
    pytest.main([__file__, "-v"])