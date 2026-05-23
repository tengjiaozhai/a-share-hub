from src.execution.paper_broker import PaperBroker

def test_paper_broker_accepts_order():
    broker = PaperBroker()
    result = broker.submit_order({"order_id": "O1", "symbol": "600519.SH", "quantity": 100})
    assert result["accepted"] is True
    assert result["status"] == "SUBMITTED"

def test_paper_broker_simulates_fill():
    broker = PaperBroker(fill_rate=1.0)
    broker.submit_order({"order_id": "O1", "quantity": 100})
    event = broker.simulate_fill("O1")
    assert event["event_type"] == "FILLED"
    assert event["fill_quantity"] == 100
