from typing import Any

from src.alpha.execution_gateway import AlphaExecutionGateway
from src.alpha.execution_models import AlphaExecutionCapability, AlphaExecutionRequest
from src.alpha.execution_service import AlphaExecutionService


class FakeGateway(AlphaExecutionGateway):
    async def submit_limit_order(self, request: Any) -> dict[str, Any]:
        return {"remote_order_id": "remote-001", "status": "SUBMITTED"}


def test_execution_service_blocks_submit_when_mode_is_manual() -> None:
    service = AlphaExecutionService(mode="manual", gateway=None)

    capability = service.get_capability()

    assert capability == AlphaExecutionCapability(mode="manual", enabled=False, reason="manual execution only")


def test_execution_service_submits_order_when_api_mode_is_enabled() -> None:
    service = AlphaExecutionService(mode="api", gateway=FakeGateway())
    request = AlphaExecutionRequest(
        ticket_id="alpha-ticket-001",
        asset_symbol="AAPLx",
        action="BUY",
        quantity=1.0,
        limit_price=210.0,
    )

    result = service.build_submission(request)

    assert result["mode"] == "api"
    assert result["asset_symbol"] == "AAPLx"
