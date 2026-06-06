from src.core.config import Settings
from src.strategy.strategy_config import StrategyConfig


def test_strategy_config_exposes_production_readiness_fields():
    settings = Settings(
        strategy_top_n=10,
        strategy_max_position_ratio=0.2,
        strategy_buy_score_threshold=0.55,
        strategy_sell_score_threshold=-0.20,
        strategy_scan_buy_threshold_a=0.55,
        strategy_scan_buy_threshold_us=0.45,
        strategy_min_confirm_bars=61,
        strategy_confirm_lookback_days=180,
        strategy_lot_size=100,
        strategy_fee_bps=3.0,
        strategy_slippage_bps=5.0,
        strategy_max_daily_loss_ratio=0.03,
    )

    config = StrategyConfig.from_settings(settings)

    assert config.scan_buy_threshold_a == 0.55
    assert config.scan_buy_threshold_us == 0.45
    assert config.min_confirm_bars == 61
    assert config.confirm_lookback_days == 180
    assert config.lot_size == 100
    assert config.fee_bps == 3.0
    assert config.slippage_bps == 5.0
    assert config.max_daily_loss_ratio == 0.03
