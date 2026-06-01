import pandas as pd
import pytest

from src.alpha.research_service import AlphaResearchService
from src.alpha.signal_engine import AlphaSignalEngine


class FakeHistoryClient:
    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[dict]:
        closes = {
            "AAPLx": [100, 102, 104, 106, 109],
            "SPYx": [500, 499, 498, 497, 496],
        }[symbol]
        return [{"close": close, "high": close + 1, "low": close - 1, "volume": 1000} for close in closes]


@pytest.mark.asyncio
async def test_research_service_ranks_candidates_and_proposes_ticket():
    service = AlphaResearchService(FakeHistoryClient(), AlphaSignalEngine(buy_threshold=0.02, sell_threshold=-0.02))

    ranked = await service.rank_watchlist(["AAPLx", "SPYx"])
    ticket = service.build_ticket_from_signal(ranked[0], thesis_prefix="phase3 auto")

    assert ranked[0]["symbol"] == "AAPLx"
    assert ranked[0]["action"] == "BUY"
    assert ticket["asset_symbol"] == "AAPLx"
    assert ticket["action"] == "BUY"