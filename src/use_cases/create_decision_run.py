from dataclasses import dataclass
from hashlib import sha256

from src.agents.llm_client import LLMClient
from src.domain.events.decision_events import DecisionRunCreated, DecisionRunFailed
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.domain.value_objects.symbol import Symbol
from src.infrastructure.event_bus.event_bus import EventBus


@dataclass
class CreateDecisionRunRequest:
    """创建决策运行请求"""
    symbol: Symbol
    mock_llm: bool = False


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
            # 构建prompt
            prompt = f"Generate a shadow trading decision for {request.symbol}."

            # 获取LLM客户端
            if request.mock_llm:
                from src.core.config import Settings
                llm_client = LLMClient(Settings(llm_provider="mock", llm_api_key=""))
            else:
                llm_client = self.llm_client or LLMClient()

            # 生成决策
            raw_output = llm_client.generate(prompt)
            if raw_output is None:
                error_msg = "LLM client returned no output"

                # 发布失败事件
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

            # 解析决策
            from src.decision.decision_runner import parse_decision_output
            decision = parse_decision_output(raw_output)

            # 构建输入快照
            from src.decision.input_builder import build_decision_input_snapshot
            input_snapshot = build_decision_input_snapshot(
                symbol=str(request.symbol),
                features={"source": "use_case", "mock_llm": request.mock_llm},
                market_context={"mode": "shadow"},
            )

            # 保存决策运行记录
            decision_run_id = self.decision_run_repository.insert_decision_run(
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

            # 发布成功事件
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
            # 发布失败事件
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
