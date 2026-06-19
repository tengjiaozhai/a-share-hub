import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from src.api.auth_security import verify_broker_signature
from src.core.config import Settings
from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.post("/broker-events")
async def receive_broker_event(
    request: Request,
    store=Depends(get_runtime_store),
    x_broker_signature: str | None = Header(default=None, alias="X-Broker-Signature"),
    x_broker_timestamp: str | None = Header(default=None, alias="X-Broker-Timestamp"),
) -> dict:
    settings = Settings()
    if not settings.broker_hmac_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="broker hmac not configured")
    body = await request.body()
    if not verify_broker_signature(body, x_broker_signature, x_broker_timestamp, settings.broker_hmac_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid broker signature")
    try:
        event = json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json body") from exc
    for required in ("event_id", "order_id", "event_type"):
        if required not in event:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"missing field: {required}")
    store.insert_broker_event(
        event_id=event["event_id"],
        order_id=event["order_id"],
        event_type=event["event_type"],
        payload=event,
    )
    return {"received": True, "event_type": event["event_type"]}
