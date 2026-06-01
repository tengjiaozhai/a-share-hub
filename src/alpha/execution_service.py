from typing import Any

from src.alpha.execution_gateway import AlphaExecutionGateway
from src.alpha.execution_models import AlphaExecutionCapability, AlphaExecutionRequest


class AlphaExecutionService:
    def __init__(self, mode: str, gateway: AlphaExecutionGateway | None) -> None:
        self._mode = mode
        self._gateway = gateway

    def get_capability(self) -> AlphaExecutionCapability:
        if self._mode == "api" and self._gateway is not None:
            return AlphaExecutionCapability(mode="api", enabled=True, reason="remote submit enabled")
        if self._mode == "manual":
            return AlphaExecutionCapability(mode="manual", enabled=False, reason="manual execution only")
        return AlphaExecutionCapability(mode=self._mode, enabled=False, reason="execution disabled")

    def build_submission(self, request: AlphaExecutionRequest) -> dict[str, Any]:
        capability = self.get_capability()
        if not capability.enabled:
            return {"mode": capability.mode, "enabled": False, "reason": capability.reason}
        return {
            "mode": capability.mode,
            "enabled": True,
            "ticket_id": request.ticket_id,
            "asset_symbol": request.asset_symbol,
            "action": request.action,
            "quantity": request.quantity,
            "limit_price": request.limit_price,
        }
