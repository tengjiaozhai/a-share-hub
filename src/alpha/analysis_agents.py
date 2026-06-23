import json

from pydantic import ValidationError

from src.agents.llm_client import LLMGenerationError
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


class AnalysisAgentError(RuntimeError):
    pass


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalize_research_payload(payload: dict, snapshot: AnalysisSnapshot) -> dict:
    allowed_ratings = {"BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"}
    rating = str(payload.get("rating") or "HOLD").upper()
    if rating not in allowed_ratings:
        rating = "HOLD"
    data_gaps = _as_list(payload.get("data_gaps")) or _as_list(snapshot.data_quality.get("missing"))
    return {
        **payload,
        "rating": rating,
        "thesis": str(payload.get("thesis") or f"{snapshot.symbol} 持仓快照已生成，结论基于行情、技术指标和可用基本面数据。"),
        "technical_view": str(
            payload.get("technical_view")
            or f"收盘价 {snapshot.close:.4f}，20日均线 {snapshot.technical.get('ma20', '--')}，60日均线 {snapshot.technical.get('ma60', '--')}。"
        ),
        "fundamental_view": str(
            payload.get("fundamental_view")
            or ("基本面数据可用。" if snapshot.fundamentals.get("status") == "ok" else "基本面数据缺失或不可用。")
        ),
        "sentiment_view": str(payload.get("sentiment_view") or "新闻/舆情数据不可用，已降低结论置信度。"),
        "catalysts": _as_list(payload.get("catalysts")),
        "risks": _as_list(payload.get("risks")) or data_gaps or ["数据覆盖不足"],
        "confidence": _as_float(payload.get("confidence"), 0.4),
        "data_gaps": data_gaps,
    }


def _normalize_trader_payload(payload: dict, snapshot: AnalysisSnapshot) -> dict:
    allowed_actions = {"BUY", "HOLD", "SELL"}
    action = str(payload.get("action") or "HOLD").upper()
    if action not in allowed_actions:
        action = "HOLD"
    stop_loss = payload.get("stop_loss")
    take_profit = payload.get("take_profit")
    return {
        **payload,
        "action": action,
        "reasoning": str(payload.get("reasoning") or "根据研究结论和当前持仓，先给出保守持有建议。"),
        "entry_low": _as_float(payload.get("entry_low"), snapshot.close),
        "entry_high": _as_float(payload.get("entry_high"), snapshot.close),
        "stop_loss": _as_float(stop_loss, round(snapshot.weighted_avg_cost * (1 + snapshot.stop_loss_ratio), 6)),
        "take_profit": _as_float(take_profit, round(snapshot.weighted_avg_cost * (1 + snapshot.take_profit_ratio), 6)),
        "position_ratio": _clamp(_as_float(payload.get("position_ratio"), 0.0), 0.0, 1.0),
    }


def _research_fallback(snapshot: AnalysisSnapshot, reason: str) -> ResearchPlan:
    payload = _normalize_research_payload(
        {
            "rating": "HOLD",
            "confidence": 0.2,
            "data_gaps": [f"LLM 输出不可用: {reason}"],
        },
        snapshot,
    )
    return ResearchPlan.model_validate(payload)


def _trader_fallback(snapshot: AnalysisSnapshot, reason: str) -> TraderProposal:
    payload = _normalize_trader_payload(
        {
            "action": "HOLD",
            "reasoning": f"LLM 交易计划输出不可用，采用保守 HOLD；先依据当前收盘价、持仓成本和止损止盈线观察。原因: {reason}",
            "position_ratio": 0.0,
        },
        snapshot,
    )
    return TraderProposal.model_validate(payload)


class ResearchManager:
    SYSTEM_PROMPT = (
        "你是持仓研究经理。只能使用输入 JSON 中的证据。"
        "输出 BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL 五档评级。"
        "数据缺失必须写入 data_gaps 并降低 confidence，不得补写未提供的新闻或财务事实。"
        "只输出合法 json，不要输出 markdown，不要输出解释。"
        "输出格式必须是："
        '{"rating":"HOLD","thesis":"证据不足，暂时观察",'
        '"technical_view":"趋势证据中性","fundamental_view":"基本面数据有限",'
        '"sentiment_view":"新闻数据不可用","catalysts":[],"risks":["数据缺失"],'
        '"confidence":0.4,"data_gaps":["news"]}'
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
            return ResearchPlan.model_validate(_normalize_research_payload(payload, snapshot))
        except (LLMGenerationError, ValidationError) as exc:
            return _research_fallback(snapshot, str(exc))


class Trader:
    SYSTEM_PROMPT = (
        "你是交易员。不要重新研究公司，只把研究计划和当前持仓转换为 BUY/HOLD/SELL。"
        "给出入场区间、止损、止盈和建议仓位。已有持仓时 BUY 表示建议加仓。"
        "只输出合法 json，不要输出 markdown，不要输出解释。"
        "输出格式必须是："
        '{"action":"HOLD","reasoning":"等待价格确认，暂不加仓",'
        '"entry_low":12.3,"entry_high":12.8,"stop_loss":11.5,'
        '"take_profit":15.0,"position_ratio":0.0}'
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
                max_tokens=1500,
            )
            return TraderProposal.model_validate(_normalize_trader_payload(payload, snapshot))
        except (LLMGenerationError, ValidationError) as exc:
            return _trader_fallback(snapshot, str(exc))
