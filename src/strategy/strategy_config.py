from __future__ import annotations
from dataclasses import dataclass
from src.core.config import Settings


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int
    max_position_ratio: float
    buy_score_threshold: float
    sell_score_threshold: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "StrategyConfig":
        return cls(
            top_n=settings.strategy_top_n,
            max_position_ratio=settings.strategy_max_position_ratio,
            buy_score_threshold=settings.strategy_buy_score_threshold,
            sell_score_threshold=settings.strategy_sell_score_threshold,
        )
