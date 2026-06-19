"""API 依赖注入。

此文件为 Worktree 2 拥有的依赖注入模块。本 Worktree 仅做最小占位实现，
供 routes 编译通过与测试运行。Worktree 2 将以实际实现覆盖。
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status


def get_current_user_id(request: Request) -> str:
    """从请求中提取当前登录用户 ID。

    占位实现：依赖 auth_middleware 已经把 user dict 写入 request.state.user。
    Worktree 2 将在此文件中重写为正式实现（可能支持 query/header 覆盖、
    未登录返回 401 等语义）。"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user.get("user_id", "")
