from fastapi import APIRouter, Depends

from src.api.auth_security import require_role
from src.api.dependencies import get_current_user
from src.core.config import Settings
from src.storage.dependencies import get_system_runtime_store
from src.storage.redis_cache import RedisCache, should_use_redis_cache
from src.storage.system_runtime_store import SystemRuntimeStore

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.post("/kill-switch/activate")
def activate_kill_switch(
    payload: dict | None = None,
    system_store: SystemRuntimeStore = Depends(get_system_runtime_store),
    _user: dict = Depends(require_role("admin")),
) -> dict:
    reason = _extract_reason(payload, default_reason="manual activate")
    system_store.insert_kill_switch_event(active=True, reason=reason)
    _sync_cached_status(active=True)
    return {"activated": True, "reason": reason}


@router.post("/kill-switch/deactivate")
def deactivate_kill_switch(
    payload: dict | None = None,
    system_store: SystemRuntimeStore = Depends(get_system_runtime_store),
    _user: dict = Depends(require_role("admin")),
) -> dict:
    reason = _extract_reason(payload, default_reason="manual deactivate")
    system_store.insert_kill_switch_event(active=False, reason=reason)
    _sync_cached_status(active=False)
    return {"deactivated": True, "reason": reason}


@router.get("/kill-switch/status")
def get_kill_switch_status(
    system_store: SystemRuntimeStore = Depends(get_system_runtime_store),
) -> dict:
    settings = Settings()
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        cache = RedisCache(settings.redis_url)
        cached = cache.get_json("kill-switch-status")
        if cached is not None:
            return cached
    payload = {"active": system_store.get_kill_switch()}
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        RedisCache(settings.redis_url).set_json("kill-switch-status", payload, settings.redis_kill_switch_ttl_seconds)
    return payload


def _extract_reason(payload: dict | None, default_reason: str) -> str:
    if isinstance(payload, dict):
        reason = payload.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    return default_reason


def _sync_cached_status(active: bool) -> None:
    settings = Settings()
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        RedisCache(settings.redis_url).set_json(
            "kill-switch-status",
            {"active": active},
            settings.redis_kill_switch_ttl_seconds,
        )