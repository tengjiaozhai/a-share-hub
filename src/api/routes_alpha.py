from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.alpha.binance_public_client import BinanceAlphaPublicClient
from src.alpha.reconciliation import reconcile_alpha_positions
from src.alpha.research_service import AlphaResearchService
from src.alpha.service import AlphaMarketService
from src.alpha.signal_engine import AlphaSignalEngine
from src.storage.dependencies import get_runtime_store
from src.storage.runtime_store import RuntimeStore

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
    notes: str


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
def create_alpha_ticket(payload: CreateAlphaTicketRequest, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    ticket_id = store.insert_alpha_ticket(**payload.model_dump())
    return {"ticket_id": ticket_id, "status": "PROPOSED"}


@router.post("/tickets/{ticket_id}/approve")
def approve_alpha_ticket(ticket_id: str, payload: ApproveAlphaTicketRequest, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    tickets = store.list_alpha_tickets()
    ticket_exists = any(t["ticket_id"] == ticket_id for t in tickets)
    if not ticket_exists:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    store.approve_alpha_ticket(ticket_id=ticket_id, operator_id=payload.operator_id)
    return {"ticket_id": ticket_id, "status": "APPROVED"}


@router.post("/tickets/{ticket_id}/fills")
def record_alpha_fill(ticket_id: str, payload: RecordAlphaFillRequest, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    tickets = store.list_alpha_tickets()
    ticket_exists = any(t["ticket_id"] == ticket_id for t in tickets)
    if not ticket_exists:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    fill_id = store.insert_alpha_manual_fill(ticket_id=ticket_id, **payload.model_dump())
    return {"ticket_id": ticket_id, "fill_id": fill_id, "recorded": True}


@router.post("/reconciliation/run")
def run_alpha_reconciliation(payload: dict, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    latest = store.get_latest_alpha_portfolio_snapshot() or {"cash_balance": 0.0}
    internal_positions = {row["symbol"]: row["quantity"] for row in store.list_alpha_positions()}
    result = reconcile_alpha_positions(
        internal_positions=internal_positions,
        external_positions=payload["external_positions"],
        internal_cash=latest["cash_balance"],
        external_cash=payload["external_cash"],
    )
    run_id = store.insert_alpha_reconciliation_run(
        source="manual",
        status=result["status"],
        discrepancies=result["discrepancies"],
    )
    return {"run_id": run_id, **result}


@router.get("/watchlist")
def list_alpha_watchlist(store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    return {"items": store.list_alpha_watchlist_items()}


class AddAlphaWatchlistRequest(BaseModel):
    symbol: str
    underlying_symbol: str
    priority: int


@router.post("/watchlist")
def add_alpha_watchlist(payload: AddAlphaWatchlistRequest, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    store.add_alpha_watchlist_item(**payload.model_dump())
    return {"stored": True, "symbol": payload.symbol}


@router.post("/research/scan")
async def scan_alpha_watchlist(
    store: RuntimeStore = Depends(get_runtime_store),
    research_service: AlphaResearchService = Depends(get_alpha_research_service),
) -> dict:
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items()]
    return {"items": await research_service.rank_watchlist(symbols)}


def _get_alpha_research_service() -> AlphaResearchService:
    """获取研究服务实例，供 propose-top-ticket 端点使用（可被测试 monkeypatch）"""
    client = httpx.AsyncClient(base_url="https://api.binance.com")
    history_client = BinanceHistoryClient(client)
    signal_engine = AlphaSignalEngine(buy_threshold=0.02, sell_threshold=-0.02)
    return AlphaResearchService(history_client, signal_engine)


@router.post("/research/propose-top-ticket")
async def propose_top_alpha_ticket(payload: dict, store: RuntimeStore = Depends(get_runtime_store)) -> dict:
    service = _get_alpha_research_service()
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items()]
    ranked = await service.rank_watchlist(symbols)
    top = ranked[0]
    ticket_payload = service.build_ticket_from_signal(top, thesis_prefix=payload["thesis_prefix"])
    ticket_payload["expires_at"] = payload.get("expires_at", "2026-06-01T16:00:00+08:00")
    ticket_id = store.insert_alpha_ticket(**ticket_payload)
    return {"ticket_id": ticket_id, **ticket_payload}
