from typing import Any

import pytest

from src.alpha.service import AlphaMarketService


class FakeAlphaClient:
    async def get_tokenized_securities(self) -> dict[str, Any]:
        return {
            "data": {
                "tokenizedStocks": [
                    {
                        "symbol": "AAPLx",
                        "underlyingSymbol": "AAPL",
                        "projectId": "alpha-aaplx",
                        "marketStatus": "TRADING",
                        "assetStatus": "ACTIVE",
                        "sharesMultiplier": "1",
                        "limitInfo": {"minQty": "0.1", "maxQty": "50"},
                    }
                ]
            }
        }


@pytest.mark.asyncio
async def test_market_service_normalizes_asset_snapshot() -> None:
    service = AlphaMarketService(FakeAlphaClient())

    snapshots = await service.list_asset_snapshots()

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.symbol == "AAPLx"
    assert snapshot.underlying_symbol == "AAPL"
    assert snapshot.market_status == "TRADING"
    assert snapshot.asset_status == "ACTIVE"
    assert snapshot.shares_multiplier == 1.0
    assert snapshot.min_qty == 0.1
    assert snapshot.max_qty == 50.0
