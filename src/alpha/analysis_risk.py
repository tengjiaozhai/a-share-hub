from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, RiskDecision, TraderProposal


def evaluate_risk(
    snapshot: AnalysisSnapshot,
    research: ResearchPlan,
    trader: TraderProposal,
    *,
    max_position_ratio: float,
) -> RiskDecision:
    pnl_ratio = snapshot.unrealized_pnl_ratio
    if pnl_ratio <= snapshot.stop_loss_ratio:
        return RiskDecision(
            action="EXIT",
            reason="收盘浮亏已达到持仓止损线",
            triggered_rules=["stop_loss_breached"],
            approved_position_ratio=0,
        )
    if research.rating == "SELL":
        return RiskDecision(
            action="EXIT",
            reason="研究结论为 SELL，原持仓逻辑已被否定",
            triggered_rules=["research_sell"],
            approved_position_ratio=0,
        )
    if pnl_ratio >= snapshot.take_profit_ratio:
        return RiskDecision(
            action="REDUCE",
            reason="收盘浮盈已达到持仓止盈线",
            triggered_rules=["take_profit_reached"],
            approved_position_ratio=max(0, snapshot.position_ratio / 2),
        )
    if trader.action == "SELL" or research.rating == "UNDERWEIGHT":
        return RiskDecision(
            action="REDUCE",
            reason="交易建议偏空或研究评级为 UNDERWEIGHT",
            triggered_rules=["directional_reduce"],
            approved_position_ratio=max(0, snapshot.position_ratio / 2),
        )
    missing = set(snapshot.data_quality.get("missing", []))
    if "technical_history" in missing:
        return RiskDecision(
            action="HOLD",
            reason="技术历史不足，禁止新增风险敞口",
            triggered_rules=["insufficient_technical_history"],
            approved_position_ratio=snapshot.position_ratio,
        )
    if snapshot.position_ratio >= max_position_ratio:
        return RiskDecision(
            action="HOLD",
            reason="当前持仓比例已达到单票上限",
            triggered_rules=["position_limit_reached"],
            approved_position_ratio=snapshot.position_ratio,
        )
    technical = snapshot.technical
    trend_ok = (
        snapshot.close > technical.get("ma20", 0) > technical.get("ma60", 0)
        and technical.get("reclaimed_ma20") is True
    )
    not_extended = technical.get("ma20_gap", 0) <= 0.05
    volume_ok = technical.get("volume_ratio_20", 0) >= 1.0
    if research.rating in {"BUY", "OVERWEIGHT"} and trader.action == "BUY" and trend_ok and not_extended and volume_ok:
        approved = min(max_position_ratio, max(snapshot.position_ratio, trader.position_ratio))
        return RiskDecision(
            action="ADD",
            reason="研究和交易方向一致，趋势回踩与成交量条件满足",
            triggered_rules=["trend_pullback_confirmed"],
            approved_position_ratio=approved,
        )
    return RiskDecision(
        action="HOLD",
        reason="未满足减仓或加仓的完整条件",
        triggered_rules=["no_action_trigger"],
        approved_position_ratio=snapshot.position_ratio,
    )
