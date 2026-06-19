from fastapi import Depends, HTTPException, Request, status


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    return str(user["user_id"])
