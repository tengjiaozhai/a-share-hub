from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.alpha.portfolio_service import AlphaPortfolioService
from src.alpha.report_service import (
    AlphaPortfolioReportService,
    normalize_report_positions,
    normalize_report_symbol,
    normalize_report_symbols,
)
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
    stop_loss_ratio = float(payload.get("stop_loss_ratio", -0.08) or -0.08)
    take_profit_ratio = float(payload.get("take_profit_ratio", 0.20) or 0.20)
    if not symbol or not buy_date or buy_price <= 0 or quantity <= 0:
        raise HTTPException(status_code=400, detail="invalid holdings entry")
    return {
        "symbol": symbol[0],
        "buy_date": buy_date,
        "buy_price": buy_price,
        "quantity": quantity,
        "stop_loss_ratio": stop_loss_ratio,
        "take_profit_ratio": take_profit_ratio,
    }


def _latest_close_price_map(symbols: list[str]) -> dict[str, float]:
    price_map: dict[str, float] = {}
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=14)
    for symbol in symbols:
        try:
            if symbol.upper().endswith(".US"):
                from src.us_stock.yahoo_provider import YahooProvider

                klines = YahooProvider().get_kline(symbol[:-3], interval="1d", range_str="1mo")
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


def _build_report_service(store: RuntimeStore) -> AlphaPortfolioReportService:
    from src.agents.llm_client import LLMClient
    from src.alpha.analysis_agents import ResearchManager, Trader
    from src.alpha.analysis_snapshot import AnalysisSnapshotBuilder
    from src.core.config import Settings

    settings = Settings()
    llm = LLMClient(settings)

    def history_loader(symbol: str) -> list[dict]:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=120)
        try:
            if symbol.upper().endswith(".US"):
                from src.us_stock.yahoo_provider import YahooProvider

                klines = YahooProvider().get_kline(symbol[:-3], interval="1d", range_str="6mo")
                return [
                    {
                        "date": (
                            k.timestamp.strftime("%Y-%m-%d")
                            if hasattr(k.timestamp, "strftime")
                            else str(k.timestamp)[:10]
                        ),
                        "close": k.close,
                        "volume": k.volume,
                    }
                    for k in klines
                ]
            else:
                from src.data.providers.akshare_provider import AkshareProvider

                bars = AkshareProvider().get_history(symbol, start_date, end_date)
                if bars is None or getattr(bars, "empty", True):
                    return []
                return bars.to_dict("records")
        except Exception:
            return []

    def fundamental_loader(symbol: str) -> dict:
        if symbol.upper().endswith(".US"):
            from src.us_stock.yahoo_provider import YahooProvider

            try:
                return YahooProvider().get_fundamental(symbol[:-3])
            except Exception:
                return {"status": "error"}
        return {"status": "ok"}

    snapshot_builder = AnalysisSnapshotBuilder(
        history_loader=history_loader,
        fundamental_loader=fundamental_loader,
    )

    return AlphaPortfolioReportService(
        store=store,
        snapshot_builder=snapshot_builder,
        research_manager=ResearchManager(llm),
        trader=Trader(llm),
        model_name=settings.llm_model,
        max_position_ratio=0.2,
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
        include_backtest: bool = True,
        backtest_window: str = "60d",
        opening_cash: float = 10_000.0,
    ) -> None:
        self.symbols = symbols or []
        self.positions = positions or []
        self.include_backtest = include_backtest
        self.backtest_window = backtest_window
        self.opening_cash = opening_cash

    def model_dump(self) -> dict:
        return {
            "symbols": self.symbols,
            "positions": self.positions,
            "include_backtest": self.include_backtest,
            "backtest_window": self.backtest_window,
            "opening_cash": self.opening_cash,
        }


@router.post("/portfolio/report")
def generate_portfolio_report(
    payload: dict,
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    service = _build_report_service(store)
    request_payload = {
        "symbols": payload.get("symbols", []),
        "positions": payload.get("positions", []),
        "include_backtest": payload.get("include_backtest", True),
        "backtest_window": payload.get("backtest_window", "60d"),
        "opening_cash": payload.get("opening_cash", 10_000.0),
    }
    request_payload["symbols"] = normalize_report_symbols(request_payload.get("symbols"))
    request_payload["positions"] = normalize_report_positions(request_payload.get("positions"))
    return service.generate_report(request_payload)


@router.get("/analysis-runs")
def list_analysis_runs(
    symbol: str | None = None,
    limit: int = 20,
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    normalized = normalize_report_symbol(symbol) if symbol else None
    safe_limit = min(max(limit, 1), 100)
    return {"items": store.list_alpha_analysis_runs(symbol=normalized, limit=safe_limit)}


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
def update_holdings_entry(entry_id: str, payload: dict, store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
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


def _classify_market(symbol: str) -> str:
    return "us" if symbol.upper().endswith(".US") else "a"


@router.get("/holdings/summary")
def get_holdings_summary(store: RuntimeStore = Depends(get_user_runtime_store)) -> dict:
    entries = store.list_alpha_holdings_entries()
    positions_by_symbol: dict[str, list[dict]] = {}
    for entry in entries:
        positions_by_symbol.setdefault(entry["symbol"], []).append(entry)

    aggregate: dict[str, dict] = {}

    for symbol, lots in positions_by_symbol.items():
        market = _classify_market(symbol)
        currency = "USD" if market == "us" else "CNY"
        total_quantity = sum(float(lot["quantity"]) for lot in lots)
        total_cost = sum(float(lot["buy_price"]) * float(lot["quantity"]) for lot in lots)
        weighted_avg_cost = total_cost / total_quantity if total_quantity > 0 else 0.0
        first_buy_date = min(lot["buy_date"] for lot in lots)
        last_buy_date = max(lot["buy_date"] for lot in lots)

        latest_price: float | None = None
        try:
            price_map = _latest_close_price_map([symbol])
            latest_price = price_map.get(symbol)
        except Exception:
            latest_price = None

        market_value = latest_price * total_quantity if latest_price is not None else 0.0
        if latest_price is not None and weighted_avg_cost > 0:
            unrealized_pnl = (latest_price - weighted_avg_cost) * total_quantity
            unrealized_pnl_ratio = (latest_price - weighted_avg_cost) / weighted_avg_cost
        else:
            unrealized_pnl = 0.0
            unrealized_pnl_ratio = 0.0

        if unrealized_pnl_ratio <= -0.08:
            alert_level = "stop_loss"
        elif unrealized_pnl_ratio >= 0.20:
            alert_level = "take_profit"
        else:
            alert_level = "ok"

        bucket = aggregate.setdefault(
            market,
            {
                "market": market,
                "currency": currency,
                "holdings_count": 0,
                "lots_count": 0,
                "total_cost": 0.0,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "_weighted_cost_sum": 0.0,
            },
        )
        bucket["holdings_count"] += 1
        bucket["lots_count"] += len(lots)
        bucket["total_cost"] += total_cost
        bucket["market_value"] += market_value
        bucket["unrealized_pnl"] += unrealized_pnl
        bucket["_weighted_cost_sum"] += total_cost

    summary: list[dict] = []
    for market_key in ("a", "us"):
        bucket = aggregate.get(market_key)
        if not bucket:
            summary.append(
                {
                    "market": market_key,
                    "currency": "USD" if market_key == "us" else "CNY",
                    "holdings_count": 0,
                    "lots_count": 0,
                    "total_cost": 0,
                    "market_value": 0,
                    "unrealized_pnl": 0,
                    "unrealized_pnl_ratio": 0,
                }
            )
            continue
        cost = bucket["_weighted_cost_sum"]
        ratio = bucket["unrealized_pnl"] / cost if cost > 0 else 0.0
        summary.append(
            {
                "market": bucket["market"],
                "currency": bucket["currency"],
                "holdings_count": bucket["holdings_count"],
                "lots_count": bucket["lots_count"],
                "total_cost": bucket["total_cost"],
                "market_value": bucket["market_value"],
                "unrealized_pnl": bucket["unrealized_pnl"],
                "unrealized_pnl_ratio": ratio,
            }
        )

    return {"summary": summary}
