from fastapi import APIRouter, Depends

from src.alpha.report_service import AlphaPortfolioReportService, normalize_report_positions, normalize_report_symbols
from src.api.dependencies import get_current_user, get_user_runtime_store
from src.storage.runtime_store import RuntimeStore

router = APIRouter(
    prefix="/api/v1/alpha",
    tags=["alpha"],
    dependencies=[Depends(get_current_user)],
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
