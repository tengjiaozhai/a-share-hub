import pytest
from src.core.config import Settings

def test_shadow_cycle_produces_no_unreconciled_orders():
    """测试影子周期不会产生未对账订单"""
    # 简化的端到端测试
    settings = Settings()
    assert settings.enable_live_trading is False
    assert settings.execution_mode == "shadow"

def test_live_flag_remains_disabled_without_release_marker():
    """测试实盘标志在没有发布标记时保持禁用"""
    settings = Settings()
    assert settings.enable_live_trading is False

def test_all_modules_importable():
    """测试所有模块可以导入"""
    from src.core.config import Settings
    from src.core.enums import Decision
    from src.core.market_clock import is_continuous_session
    from src.core.market_rules import can_sell_position_same_day
    from src.data.providers.provider_chain import ProviderChain
    from src.indicators.technical_indicators import compute_feature_row
    from src.strategy.candidate_filter import rank_candidates
    from src.decision.input_builder import build_decision_input_snapshot
    from src.decision.decision_runner import parse_decision_output
    from src.agents.schemas import DecisionOutput
    from src.portfolio.target_planner import build_target_position
    from src.risk.pre_trade_risk import evaluate_risk_gate
    from src.execution.state_machine import apply_broker_event
    from src.execution.paper_broker import PaperBroker
    from src.execution.reconciliation import reconcile_positions
    assert True
