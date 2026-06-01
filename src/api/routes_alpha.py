from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.alpha.binance_public_client import BinanceAlphaPublicClient
from src.alpha.service import AlphaMarketService
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
