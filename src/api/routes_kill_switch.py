from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.post("/kill-switch/activate")
def activate_kill_switch(store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(True)
    return {"activated": True}


@router.post("/kill-switch/deactivate")
def deactivate_kill_switch(store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(False)
    return {"deactivated": True}


@router.get("/kill-switch/status")
def get_kill_switch_status(store=Depends(get_runtime_store)) -> dict:
    return {"active": store.get_kill_switch()}
