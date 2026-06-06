from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int
    max_position_ratio: float
    buy_score_threshold: float
    sell_score_threshold: float
    scan_buy_threshold_a: float
    scan_buy_threshold_us: float
    min_confirm_bars: int
    confirm_lookback_days: int
    lot_size: int
    fee_bps: float
    slippage_bps: float
    max_daily_loss_ratio: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "StrategyConfig":
        return cls(
            top_n=settings.strategy_top_n,
            max_position_ratio=settings.strategy_max_position_ratio,
            buy_score_threshold=settings.strategy_buy_score_threshold,
            sell_score_threshold=settings.strategy_sell_score_threshold,
            scan_buy_threshold_a=settings.strategy_scan_buy_threshold_a,
            scan_buy_threshold_us=settings.strategy_scan_buy_threshold_us,
            min_confirm_bars=settings.strategy_min_confirm_bars,
            confirm_lookback_days=settings.strategy_confirm_lookback_days,
            lot_size=settings.strategy_lot_size,
            fee_bps=settings.strategy_fee_bps,
            slippage_bps=settings.strategy_slippage_bps,
            max_daily_loss_ratio=settings.strategy_max_daily_loss_ratio,
        )
