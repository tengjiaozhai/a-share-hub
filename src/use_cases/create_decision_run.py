from dataclasses import dataclass
from hashlib import sha256

from src.agents.llm_client import LLMClient
from src.core.tenant import SYSTEM_TENANT
from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.domain.value_objects.symbol import Symbol
from src.infrastructure.event_bus.event_bus import EventBus


@dataclass
class CreateDecisionRunRequest:
    """创建决策运行请求"""

    symbol: Symbol
    mock_llm: bool = False
    user_id: str = SYSTEM_TENANT.user_id


@dataclass
class CreateDecisionRunResponse:
    """创建决策运行响应"""
    success: bool
    decision_run_id: str | None = None
    error: str | None = None


class CreateDecisionRunUseCase:
    """创建决策运行用例"""

    def __init__(
        self,
        decision_run_repository: DecisionRunRepository,
        event_bus: EventBus | None = None,
        llm_client: LLMClient | None = None,
    ):
        self.decision_run_repository = decision_run_repository
        self.event_bus = event_bus
        self.llm_client = llm_client

    def execute(self, request: CreateDecisionRunRequest) -> CreateDecisionRunResponse:
        """执行创建决策运行"""
        try:
            prompt = f"Generate a shadow trading decision for {request.symbol}."

            if request.mock_llm:
                from src.core.config import Settings
                llm_client = LLMClient(Settings(llm_provider="mock", llm_api_key=""))
            else:
                llm_client = self.llm_client or LLMClient()

            raw_output = llm_client.generate(prompt)
            if raw_output is None:
                error_msg = "LLM client returned no output"

                if self.event_bus:
                    self.event_bus.publish(DecisionRunFailed(
                        symbol=str(request.symbol),
                        error=error_msg,
                        model_name=llm_client.model,
                    ))

                return CreateDecisionRunResponse(
                    success=False,
                    error=error_msg
                )

            from src.decision.decision_runner import parse_decision_output
            decision = parse_decision_output(raw_output)

            from src.decision.input_builder import build_decision_input_snapshot
            input_snapshot = build_decision_input_snapshot(
                symbol=str(request.symbol),
                features={"source": "use_case", "mock_llm": request.mock_llm},
                market_context={"mode": "shadow"},
            )

            decision_run_id = self.decision_run_repository.insert_decision_run(
                user_id=request.user_id,
                symbol=str(request.symbol),
                prompt_hash=sha256(prompt.encode("utf-8")).hexdigest(),
                model_name=llm_client.model,
                raw_output=raw_output,
                parsed_action=decision.action,
                confidence=decision.confidence,
                target_position_ratio=decision.target_position_ratio,
                reason=decision.reason,
                input_snapshot=input_snapshot,
            )

            if self.event_bus:
                self.event_bus.publish(DecisionRunCreated(
                    decision_run_id=decision_run_id,
                    symbol=str(request.symbol),
                    action=decision.action,
                    confidence=decision.confidence,
                    target_position_ratio=decision.target_position_ratio,
                    reason=decision.reason,
                    model_name=llm_client.model,
                ))

            return CreateDecisionRunResponse(
                success=True,
                decision_run_id=decision_run_id,
            )

        except Exception as e:
            if self.event_bus:
                self.event_bus.publish(DecisionRunFailed(
                    symbol=str(request.symbol),
                    error=str(e),
                    model_name=getattr(llm_client, 'model', 'unknown'),
                ))

            return CreateDecisionRunResponse(
                success=False,
                error=str(e)
            )
