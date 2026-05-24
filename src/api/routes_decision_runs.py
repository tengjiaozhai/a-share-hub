from fastapi import APIRouter, Depends, HTTPException

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/decision-runs")
def list_decision_runs(store=Depends(get_runtime_store)) -> list[dict]:
    return store.list_decision_runs()


@router.get("/decision-runs/{decision_run_id}")
def get_decision_run(decision_run_id: str, store=Depends(get_runtime_store)) -> dict:
    record = store.get_decision_run(decision_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="decision run not found")
    return record
