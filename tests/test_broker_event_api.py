from src.api.routes_broker_events import receive_broker_event

def test_receive_broker_event():
    result = receive_broker_event({"event_type": "FILLED", "order_id": "O1"})
    assert result["received"] is True
    assert result["event_type"] == "FILLED"
