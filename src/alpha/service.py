from src.alpha.models import AlphaAssetSnapshot


class AlphaMarketService:
    def __init__(self, client) -> None:
        self._client = client

    async def list_asset_snapshots(self) -> list[AlphaAssetSnapshot]:
        payload = await self._client.get_tokenized_securities()
        rows = payload.get("data", {}).get("tokenizedStocks", [])
        return [
            AlphaAssetSnapshot(
                symbol=row["symbol"],
                underlying_symbol=row.get("underlyingSymbol", ""),
                project_id=row.get("projectId", row["symbol"]),
                market_status=row.get("marketStatus", "UNKNOWN"),
                asset_status=row.get("assetStatus", "UNKNOWN"),
                shares_multiplier=float(row.get("sharesMultiplier", "1")),
                min_qty=float(row["limitInfo"]["minQty"]) if row.get("limitInfo", {}).get("minQty") else None,
                max_qty=float(row["limitInfo"]["maxQty"]) if row.get("limitInfo", {}).get("maxQty") else None,
            )
            for row in rows
        ]
