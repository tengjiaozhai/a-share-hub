from src.execution.reconciliation import detect_unreconciled_state, reconcile_positions

def test_duplicate_event_does_not_create_drift():
    plan = {"client_order_id": "A1", "filled_quantity": 40}
    broker = {"client_order_id": "A1", "filled_quantity": 40}
    assert detect_unreconciled_state(plan, broker) is False

def test_detects_drift():
    plan = {"filled_quantity": 40}
    broker = {"filled_quantity": 30}
    assert detect_unreconciled_state(plan, broker) is True

def test_reconcile_positions_matches():
    system = {"600519.SH": 100, "300750.SZ": 50}
    broker = {"600519.SH": 100, "300750.SZ": 50}
    result = reconcile_positions(system, broker)
    assert result["reconciled"] is True

def test_reconcile_positions_detects_mismatch():
    system = {"600519.SH": 100}
    broker = {"600519.SH": 80}
    result = reconcile_positions(system, broker)
    assert result["reconciled"] is False
    assert "600519.SH" in result["discrepancies"]
