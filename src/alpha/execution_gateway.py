from abc import ABC, abstractmethod
from typing import Any


class AlphaExecutionGateway(ABC):
    @abstractmethod
    async def submit_limit_order(self, request: Any) -> dict[str, Any]:
        raise NotImplementedError
