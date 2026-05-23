from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.post("/kill-switch/activate")
def activate_kill_switch() -> dict:
    """激活紧急停止"""
    return {"activated": True}

@router.post("/kill-switch/deactivate")
def deactivate_kill_switch() -> dict:
    """停用紧急停止"""
    return {"deactivated": True}

@router.get("/kill-switch/status")
def get_kill_switch_status() -> dict:
    """获取紧急停止状态"""
    return {"active": False}
