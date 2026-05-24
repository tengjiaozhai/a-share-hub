from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.post("/broker-events")
def receive_broker_event(event: dict, store=Depends(get_runtime_store)) -> dict:
    store.insert_broker_event(
        event_id=event["event_id"],
        order_id=event["order_id"],
        event_type=event["event_type"],
        payload=event,
    )
    return {"received": True, "event_type": event["event_type"]}
