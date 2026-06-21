from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.alpha.report_service import AlphaPortfolioReportService, normalize_report_positions, normalize_report_symbols
from src.alpha.portfolio_service import AlphaPortfolioService
from src.api.dependencies import get_current_user, get_user_runtime_store
from src.storage.runtime_store import RuntimeStore

router = APIRouter(
    prefix="/api/v1/alpha",
    tags=["alpha"],
    dependencies=[Depends(get_current_user)],
)


def _normalize_holdings_entry(payload: dict) -> dict:
    symbol = normalize_report_symbols([payload.get("symbol")])
    buy_date = str(payload.get("buy_date") or "").strip()
    buy_price = float(payload.get("buy_price", 0.0) or 0.0)
    quantity = float(payload.get("quantity", 0.0) or 0.0)
    if not symbol or not buy_date or buy_price <= 0 or quantity <= 0:
        raise HTTPException(status_code=400, detail="invalid holdings entry")
    return {
        "symbol": symbol[0],
        "buy_date": buy_date,
        "buy_price": buy_price,
        "quantity": quantity,
    }


def _yahoo_symbol(symbol: str) -> str:
    return symbol[:-3] if symbol.upper().endswith(".US") else symbol


def _latest_close_price_map(symbols: list[str]) -> dict[str, float]:
    price_map: dict[str, float] = {}
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=14)
    for symbol in symbols:
        try:
            if symbol.upper().endswith(".US"):
                from src.us_stock.yahoo_provider import YahooProvider

                klines = YahooProvider().get_kline(_yahoo_symbol(symbol), interval="1d", range_str="1mo")
                if klines:
                    price_map[symbol] = float(klines[-1].close)
                    continue
            else:
                from src.data.providers.akshare_provider import AkshareProvider

                bars = AkshareProvider().get_history(symbol, start_date, end_date)
                if bars is not None and not getattr(bars, "empty", True):
                    price_map[symbol] = float(bars.iloc[-1]["close"])
        except Exception:
            continue
    return price_map


def _rebuild_holdings_portfolio(store: RuntimeStore) -> None:
    symbols = [entry["symbol"] for entry in store.list_alpha_holdings_entries()]
    AlphaPortfolioService(store=store).rebuild_from_holdings_entries(
        price_map=_latest_close_price_map(sorted(set(symbols))),
    )


class GeneratePortfolioReportRequest:
    class PositionLot:
        def __init__(self, buy_date: str, buy_price: float, quantity: float) -> None:
            self.buy_date = buy_date
            self.buy_price = buy_price
            self.quantity = quantity

    class PositionInput:
        def __init__(self, symbol: str, lots: list | None = None) -> None:
            self.symbol = symbol
            self.lots = lots or []

    def __init__(
        self,
        symbols: list[str] | None = None,
        positions: list[dict] | None = None,
        include_shadow: bool = True,
        include_backtest: bool = True,
        backtest_window: str = "60d",
        opening_cash: float = 10_000.0,
    ) -> None:
        self.symbols = symbols or []
        self.positions = positions or []
        self.include_shadow = include_shadow
        self.include_backtest = include_backtest
        self.backtest_window = backtest_window
        self.opening_cash = opening_cash

    def model_dump(self) -> dict:
        return {
            "symbols": self.symbols,
            "positions": self.positions,
            "include_shadow": self.include_shadow,
            "include_backtest": self.include_backtest,
            "backtest_window": self.backtest_window,
            "opening_cash": self.opening_cash,
        }


@router.post("/portfolio/report")
def generate_portfolio_report(
    payload: dict,
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    service = AlphaPortfolioReportService(store=store)
    request_payload = {
        "symbols": payload.get("symbols", []),
        "positions": payload.get("positions", []),
        "include_shadow": payload.get("include_shadow", True),
        "include_backtest": payload.get("include_backtest", True),
        "backtest_window": payload.get("backtest_window", "60d"),
        "opening_cash": payload.get("opening_cash", 10_000.0),
    }
    request_payload["symbols"] = normalize_report_symbols(request_payload.get("symbols"))
    request_payload["positions"] = normalize_report_positions(request_payload.get("positions"))
    return service.generate_report(request_payload)


@router.get("/holdings")
def list_holdings_entries(store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    return {"items": store.list_alpha_holdings_entries()}


@router.post("/holdings")
def create_holdings_entry(payload: dict, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    normalized = _normalize_holdings_entry(payload)
    entry_id = store.insert_alpha_holdings_entry(**normalized)
    _rebuild_holdings_portfolio(store)
    return next(item for item in store.list_alpha_holdings_entries() if item["entry_id"] == entry_id)


@router.put("/holdings/{entry_id}")
def update_holdings_entry(
    entry_id: str,
    payload: dict,
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    normalized = _normalize_holdings_entry(payload)
    store.update_alpha_holdings_entry(entry_id=entry_id, **normalized)
    _rebuild_holdings_portfolio(store)
    for item in store.list_alpha_holdings_entries():
        if item["entry_id"] == entry_id:
            return item
    raise HTTPException(status_code=404, detail="holdings entry not found")


@router.delete("/holdings/{entry_id}")
def delete_holdings_entry(entry_id: str, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    store.delete_alpha_holdings_entry(entry_id)
    _rebuild_holdings_portfolio(store)
    return {"ok": True}
