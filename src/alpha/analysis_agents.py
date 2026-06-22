import json

from pydantic import ValidationError

from src.agents.llm_client import LLMGenerationError
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


class AnalysisAgentError(RuntimeError):
    pass


class ResearchManager:
    SYSTEM_PROMPT = (
        "你是持仓研究经理。只能使用输入 JSON 中的证据。"
        "输出 BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL 五档评级。"
        "数据缺失必须写入 data_gaps 并降低 confidence，不得补写未提供的新闻或财务事实。"
        "只输出合法 JSON。"
    )

    def __init__(self, llm) -> None:
        self._llm = llm

    def analyze(self, snapshot: AnalysisSnapshot) -> ResearchPlan:
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=snapshot.model_dump_json(),
                temperature=0.2,
                max_tokens=1400,
            )
            return ResearchPlan.model_validate(payload)
        except (LLMGenerationError, ValidationError) as exc:
            raise AnalysisAgentError(f"research manager failed: {exc}") from exc


class Trader:
    SYSTEM_PROMPT = (
        "你是交易员。不要重新研究公司，只把研究计划和当前持仓转换为 BUY/HOLD/SELL。"
        "给出入场区间、止损、止盈和建议仓位。已有持仓时 BUY 表示建议加仓。"
        "只输出合法 JSON。"
    )

    def __init__(self, llm) -> None:
        self._llm = llm

    def propose(self, snapshot: AnalysisSnapshot, research: ResearchPlan) -> TraderProposal:
        context = {"snapshot": snapshot.model_dump(), "research": research.model_dump()}
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True),
                temperature=0.1,
                max_tokens=1000,
            )
            return TraderProposal.model_validate(payload)
        except (LLMGenerationError, ValidationError) as exc:
            raise AnalysisAgentError(f"trader failed: {exc}") from exc
