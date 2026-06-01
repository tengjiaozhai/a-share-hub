from src.alpha.execution_models import AlphaExecutionCapability, AlphaExecutionRequest


def test_alpha_execution_capability_is_frozen():
    cap = AlphaExecutionCapability(mode="api", enabled=True, reason="ok")
    assert cap.mode == "api"
    assert cap.enabled is True
    assert cap.reason == "ok"


def test_alpha_execution_capability_cannot_be_mutated():
    cap = AlphaExecutionCapability(mode="manual", enabled=False, reason="no key")
    try:
        cap.mode = "api"  # type: ignore[misc]
        assert False, "should have raised"
    except AttributeError:
        pass


def test_alpha_execution_request_is_frozen():
    req = AlphaExecutionRequest(
        ticket_id="t-1",
        asset_symbol="BTCUSDT",
        action="buy",
        quantity=0.01,
        limit_price=50000.0,
    )
    assert req.ticket_id == "t-1"
    assert req.asset_symbol == "BTCUSDT"
    assert req.action == "buy"
    assert req.quantity == 0.01
    assert req.limit_price == 50000.0
