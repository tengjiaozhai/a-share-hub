from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.alpha.binance_public_client import BinanceAlphaPublicClient
from src.alpha.execution_models import AlphaExecutionRequest
from src.alpha.execution_service import AlphaExecutionService
from src.alpha.portfolio_service import AlphaPortfolioService
from src.alpha.reconciliation import reconcile_alpha_positions
from src.alpha.report_service import AlphaPortfolioReportService
from src.alpha.research_service import AlphaResearchService
from src.alpha.service import AlphaMarketService
from src.alpha.signal_engine import AlphaSignalEngine
from src.api.dependencies import get_current_user_id
from src.storage.dependencies import get_runtime_store
from src.storage.runtime_store import RuntimeStore


def _get_alpha_execution_service() -> AlphaExecutionService:
    return AlphaExecutionService(mode="manual", gateway=None)

router = APIRouter(prefix="/api/v1/alpha", tags=["alpha"])


class CreateAlphaTicketRequest(BaseModel):
    asset_symbol: str
    underlying_symbol: str
    action: str
    thesis: str
    suggested_quantity: float
    suggested_limit_price: float
    expires_at: str


class ApproveAlphaTicketRequest(BaseModel):
    operator_id: str


class RecordAlphaFillRequest(BaseModel):
    operator_id: str
    executed_quantity: float
    executed_price: float
    executed_at: str | None = None
    notes: str
    rebuild_opening_cash: float | None = None
    rebuild_price_map: dict[str, float] = {}


class RebuildAlphaPortfolioRequest(BaseModel):
    opening_cash: float
    price_map: dict[str, float] = {}


class GeneratePortfolioReportRequest(BaseModel):
    symbols: list[str] = []
    include_shadow: bool = True
    include_backtest: bool = True
    backtest_window: str = "60d"
    opening_cash: float = 10_000.0


async def get_alpha_service() -> AsyncGenerator[AlphaMarketService, None]:
    client = httpx.AsyncClient(base_url="https://www.binance.com")
    service = AlphaMarketService(BinanceAlphaPublicClient(client))
    try:
        yield service
    finally:
        await client.aclose()


class BinanceHistoryClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[dict]:
        response = await self._http.get(
            "/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        response.raise_for_status()
        raw = response.json()
        return [
            {
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            }
            for item in raw
        ]


async def get_alpha_research_service() -> AsyncGenerator[AlphaResearchService, None]:
    client = httpx.AsyncClient(base_url="https://api.binance.com")
    history_client = BinanceHistoryClient(client)
    signal_engine = AlphaSignalEngine(buy_threshold=0.02, sell_threshold=-0.02)
    service = AlphaResearchService(history_client, signal_engine)
    try:
        yield service
    finally:
        await client.aclose()


@router.get("/assets")
async def list_alpha_assets(service: AlphaMarketService = Depends(get_alpha_service)) -> dict[str, Any]:
    try:
        snapshots = await service.list_asset_snapshots()
        return {
            "items": [
                {
                    "symbol": item.symbol,
                    "underlying_symbol": item.underlying_symbol,
                    "project_id": item.project_id,
                    "market_status": item.market_status,
                    "asset_status": item.asset_status,
                    "shares_multiplier": item.shares_multiplier,
                    "min_qty": item.min_qty,
                    "max_qty": item.max_qty,
                }
                for item in snapshots
            ]
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Binance API error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/tickets")
def create_alpha_ticket(
    payload: CreateAlphaTicketRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    ticket_id = store.insert_alpha_ticket(user_id=user_id, **payload.model_dump())
    return {"ticket_id": ticket_id, "status": "PROPOSED"}


@router.post("/tickets/{ticket_id}/approve")
def approve_alpha_ticket(
    ticket_id: str,
    payload: ApproveAlphaTicketRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    tickets = store.list_alpha_tickets(user_id)
    ticket_exists = any(t["ticket_id"] == ticket_id for t in tickets)
    if not ticket_exists:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    store.approve_alpha_ticket(user_id=user_id, ticket_id=ticket_id, operator_id=payload.operator_id)
    return {"ticket_id": ticket_id, "status": "APPROVED"}


@router.post("/tickets/{ticket_id}/fills")
def record_alpha_fill(
    ticket_id: str,
    payload: RecordAlphaFillRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    tickets = store.list_alpha_tickets(user_id)
    ticket_exists = any(t["ticket_id"] == ticket_id for t in tickets)
    if not ticket_exists:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    payload_dict = payload.model_dump()
    rebuild_opening_cash = payload_dict.pop("rebuild_opening_cash")
    rebuild_price_map = payload_dict.pop("rebuild_price_map")
    fill_id = store.insert_alpha_manual_fill(user_id=user_id, ticket_id=ticket_id, **payload_dict)
    response = {"ticket_id": ticket_id, "fill_id": fill_id, "recorded": True, "portfolio_rebuilt": False}
    if rebuild_opening_cash is not None:
        response["portfolio"] = AlphaPortfolioService(store, user_id=user_id).rebuild_portfolio(
            opening_cash=rebuild_opening_cash,
            price_map=rebuild_price_map,
        )
        response["portfolio_rebuilt"] = True
    return response


@router.get("/portfolio")
def get_alpha_portfolio(
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    return AlphaPortfolioService(store, user_id=user_id).load_portfolio()


@router.post("/portfolio/rebuilds")
def rebuild_alpha_portfolio(
    payload: RebuildAlphaPortfolioRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    return AlphaPortfolioService(store, user_id=user_id).rebuild_portfolio(
        opening_cash=payload.opening_cash,
        price_map=payload.price_map,
    )


@router.post("/portfolio/report")
def generate_portfolio_report(
    payload: GeneratePortfolioReportRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    service = AlphaPortfolioReportService(store=store, user_id=user_id)
    return service.generate_report(payload.model_dump())


@router.post("/reconciliation/run")
def run_alpha_reconciliation(
    payload: dict,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    latest = store.get_latest_alpha_portfolio_snapshot(user_id) or {"cash_balance": 0.0}
    internal_positions = {row["symbol"]: row["quantity"] for row in store.list_alpha_positions(user_id)}
    result = reconcile_alpha_positions(
        internal_positions=internal_positions,
        external_positions=payload["external_positions"],
        internal_cash=latest["cash_balance"],
        external_cash=payload["external_cash"],
    )
    run_id = store.insert_alpha_reconciliation_run(
        user_id=user_id,
        source="manual",
        status=result["status"],
        discrepancies=result["discrepancies"],
    )
    return {"run_id": run_id, **result}


@router.get("/watchlist")
def list_alpha_watchlist(
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    return {"items": store.list_alpha_watchlist_items(user_id)}


class AddAlphaWatchlistRequest(BaseModel):
    symbol: str
    underlying_symbol: str
    priority: int


@router.post("/watchlist")
def add_alpha_watchlist(
    payload: AddAlphaWatchlistRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    store.add_alpha_watchlist_item(user_id=user_id, **payload.model_dump())
    return {"stored": True, "symbol": payload.symbol}


def _apply_holdings_guidance(items: list[dict], positions: list[dict]) -> list[dict]:
    held_positions = {
        row["symbol"]: row
        for row in positions
        if float(row.get("quantity", 0.0)) > 0
    }
    enriched = []
    for item in items:
        action = str(item.get("action", "HOLD")).upper()
        position = held_positions.get(item["symbol"])
        is_held = position is not None
        if action == "BUY":
            guidance = "add_or_watch" if is_held else "new_position_candidate"
        elif action == "SELL":
            guidance = "reduce_or_exit" if is_held else "ignore_no_position"
        else:
            guidance = "watch_only"
        enriched.append(
            {
                **item,
                "is_held": is_held,
                "held_quantity": position["quantity"] if position else 0.0,
                "portfolio_guidance": guidance,
            }
        )
    return enriched


@router.post("/research/scan")
async def scan_alpha_watchlist(
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
    research_service: AlphaResearchService = Depends(get_alpha_research_service),
) -> dict:
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items(user_id)]
    ranked = await research_service.rank_watchlist(symbols)
    return {"items": _apply_holdings_guidance(ranked, store.list_alpha_positions(user_id))}


class ProposeTopTicketRequest(BaseModel):
    thesis_prefix: str
    expires_at: str | None = None


@router.post("/research/propose-top-ticket")
async def propose_top_alpha_ticket(
    payload: ProposeTopTicketRequest,
    store: RuntimeStore = Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
    research_service: AlphaResearchService = Depends(get_alpha_research_service),
) -> dict:
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items(user_id)]
    if not symbols:
        raise HTTPException(status_code=400, detail="Watchlist is empty")
    ranked = await research_service.rank_watchlist(symbols)
    if not ranked:
        raise HTTPException(status_code=400, detail="No candidates found")
    top = ranked[0]
    ticket_payload = research_service.build_ticket_from_signal(top, thesis_prefix=payload.thesis_prefix)
    ticket_payload["expires_at"] = payload.expires_at or "2026-06-01T16:00:00+08:00"
    ticket_id = store.insert_alpha_ticket(user_id=user_id, **ticket_payload)
    return {"ticket_id": ticket_id, **ticket_payload}


@router.get("/capabilities")
def get_alpha_capabilities() -> dict:
    capability = _get_alpha_execution_service().get_capability()
    return capability if isinstance(capability, dict) else capability.__dict__


@router.post("/orders/preview")
def preview_alpha_order(payload: dict) -> dict:
    request = AlphaExecutionRequest(**payload)
    submission = _get_alpha_execution_service().build_submission(request)
    return submission


@router.post("/orders/submit")
def submit_alpha_order(
    payload: dict,
    store=Depends(get_runtime_store),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    request = AlphaExecutionRequest(**payload)
    submission = _get_alpha_execution_service().build_submission(request)
    if not submission["enabled"]:
        raise HTTPException(status_code=409, detail=submission["reason"])
    attempt_id = store.insert_alpha_api_order_attempt(
        user_id=user_id,
        ticket_id=request.ticket_id,
        asset_symbol=request.asset_symbol,
        action=request.action,
        quantity=request.quantity,
        limit_price=request.limit_price,
        mode=submission["mode"],
        status="SUBMITTED",
        remote_order_id=None,
        response_payload=submission,
    )
    return {"attempt_id": attempt_id, **submission}
