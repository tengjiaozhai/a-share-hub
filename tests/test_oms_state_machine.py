from src.execution.state_machine import apply_broker_event, create_initial_order_state

def test_partial_fill_keeps_order_open():
    state = create_initial_order_state("O1", "600519.SH", 100, "BUY")
    event = {"event_type": "PARTIAL_FILL", "fill_quantity": 40}
    next_state = apply_broker_event(state, event)
    assert next_state["status"] == "PARTIALLY_FILLED"
    assert next_state["filled_quantity"] == 40

def test_full_fill_closes_order():
    state = create_initial_order_state("O2", "300750.SZ", 100, "SELL")
    event = {"event_type": "FILLED"}
    next_state = apply_broker_event(state, event)
    assert next_state["status"] == "FILLED"
    assert next_state["filled_quantity"] == 100

def test_cancel_order():
    state = create_initial_order_state("O3", "000001.SZ", 50, "BUY")
    event = {"event_type": "CANCELLED"}
    next_state = apply_broker_event(state, event)
    assert next_state["status"] == "CANCELLED"
