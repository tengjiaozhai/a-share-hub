import json
from src.agents.schemas import DecisionOutput

def parse_decision_output(raw: str) -> DecisionOutput:
    """解析LLM输出，失败时降级为HOLD"""
    try:
        payload = json.loads(raw)
        return DecisionOutput.model_validate(payload)
    except Exception:
        return DecisionOutput(
            symbol="UNKNOWN",
            action="HOLD",
            confidence=0,
            target_position_ratio=0.0,
            reason="LLM output parse failed",
        )

def create_decision_run(symbol: str, prompt_hash: str, input_snapshot: dict) -> dict:
    """创建决策运行记录"""
    return {
        "symbol": symbol,
        "prompt_hash": prompt_hash,
        "input_snapshot": input_snapshot,
    }

def build_decision_run_record(
    raw: str,
    symbol: str,
    prompt_hash: str,
    input_snapshot: dict,
    model_name: str,
) -> dict:
    """构建可持久化的决策记录"""
    decision = parse_decision_output(raw)
    return {
        "symbol": symbol,
        "prompt_hash": prompt_hash,
        "model_name": model_name,
        "raw_output": raw,
        "parsed_action": decision.action,
        "confidence": decision.confidence,
        "target_position_ratio": decision.target_position_ratio,
        "reason": decision.reason,
        "input_snapshot": input_snapshot,
    }
