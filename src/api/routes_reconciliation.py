from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/reconciliation/status")
def get_reconciliation_status(store=Depends(get_runtime_store)) -> dict:
    return store.get_reconciliation_status()
