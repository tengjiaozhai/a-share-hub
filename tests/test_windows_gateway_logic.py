from windows_agent.local_risk_check import local_gate
from windows_agent.xtquant_adapter import XtQuantAdapter
from windows_agent.heartbeat import create_heartbeat

def test_local_gate_rejects_when_trader_terminal_disconnected():
    result = local_gate(
        trader_connected=False,
        available_cash=100000,
        requested_value=20000,
    )
    assert result["approved"] is False
    assert result["reason"] == "trader disconnected"

def test_local_gate_approves_when_connected():
    result = local_gate(
        trader_connected=True,
        available_cash=100000,
        requested_value=20000,
    )
    assert result["approved"] is True

def test_xtquant_adapter_submit_order():
    adapter = XtQuantAdapter()
    adapter.connect()
    result = adapter.submit_order({"plan_id": "P1"})
    assert result["accepted"] is True

def test_heartbeat_structure():
    heartbeat = create_heartbeat()
    assert "agent_id" in heartbeat
    assert "timestamp" in heartbeat
    assert "status" in heartbeat
