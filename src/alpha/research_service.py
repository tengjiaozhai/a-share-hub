import pandas as pd


class AlphaResearchService:
    def __init__(self, history_client, signal_engine) -> None:
        self._history_client = history_client
        self._signal_engine = signal_engine

    async def rank_watchlist(self, symbols: list[str]) -> list[dict]:
        ranked = []
        for symbol in symbols:
            candles = await self._history_client.get_klines(symbol=symbol, interval="1h", limit=30)
            frame = pd.DataFrame(candles)
            signal = self._signal_engine.score_asset(symbol=symbol, candles=frame)
            ranked.append(
                {"symbol": signal.symbol, "score": signal.score, "action": signal.action, "reason": signal.reason}
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)

    def build_ticket_from_signal(self, signal: dict, thesis_prefix: str) -> dict:
        return {
            "asset_symbol": signal["symbol"],
            "underlying_symbol": signal["symbol"].removesuffix("x"),
            "action": signal["action"],
            "thesis": f"{thesis_prefix}: {signal['reason']}",
            "suggested_quantity": 1.0,
            "suggested_limit_price": 0.0,
        }
