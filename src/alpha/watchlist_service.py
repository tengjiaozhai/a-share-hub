class AlphaWatchlistService:
    def __init__(self, store) -> None:
        self._store = store

    def list_symbols(self) -> list[str]:
        return [item["symbol"] for item in self._store.list_alpha_watchlist_items()]
