from fastapi import Depends, HTTPException, Request, status

from src.core.tenant import TenantContext
from src.storage.dependencies import get_runtime_engine
from src.storage.runtime_store import RuntimeStore


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    return str(user["user_id"])


def get_tenant_context(user_id: str = Depends(get_current_user_id)) -> TenantContext:
    return TenantContext(user_id)


def get_user_runtime_store(
    tenant: TenantContext = Depends(get_tenant_context),
) -> RuntimeStore:
    return RuntimeStore(get_runtime_engine(), tenant)
