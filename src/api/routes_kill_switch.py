from fastapi import APIRouter, Depends

from src.core.config import Settings
from src.storage.dependencies import get_runtime_store
from src.storage.redis_cache import RedisCache, should_use_redis_cache

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
    settings = Settings()
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        cache = RedisCache(settings.redis_url)
        cached = cache.get_json("kill-switch-status")
        if cached is not None:
            return cached
    payload = {"active": store.get_kill_switch()}
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        RedisCache(settings.redis_url).set_json("kill-switch-status", payload, settings.redis_kill_switch_ttl_seconds)
    return payload
