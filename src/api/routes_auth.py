from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.api.auth_page.render import render_login_html, render_register_html
from src.api.auth_security import create_auth_token, hash_password, verify_password
from src.core.config import Settings
from src.storage.auth_store import AuthStore
from src.storage.dependencies import get_runtime_store

router = APIRouter()


def _auth_store() -> AuthStore:
    return AuthStore(get_runtime_store().engine)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> str:
    return render_login_html(
        next_url=request.query_params.get("next", "/dashboard"),
        error=request.query_params.get("error", ""),
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> str:
    return render_register_html(
        next_url=request.query_params.get("next", "/dashboard"),
        error=request.query_params.get("error", ""),
    )


@router.post("/api/v1/auth/register")
async def register(request: Request):
    data, wants_json = await _read_payload(request)
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", password))
    next_url = str(data.get("next", "/dashboard")) or "/dashboard"

    if not username or not email or not password:
        return _error("/register", "请填写用户名、邮箱和密码", next_url, wants_json)
    if password != confirm_password:
        return _error("/register", "两次输入的密码不一致", next_url, wants_json)
    if len(password) < 8:
        return _error("/register", "密码至少需要 8 位", next_url, wants_json)

    store = _auth_store()
    if store.get_user_by_account(username) or store.get_user_by_account(email):
        return _error("/register", "用户名或邮箱已存在", next_url, wants_json, status_code=409)

    user = store.create_user(username, email, hash_password(password), role="user")
    return _login_response(user, next_url, wants_json)


@router.post("/api/v1/auth/login")
async def login(request: Request):
    data, wants_json = await _read_payload(request)
    account = str(data.get("account", "")).strip()
    password = str(data.get("password", ""))
    next_url = str(data.get("next", "/dashboard")) or "/dashboard"

    user = _auth_store().get_user_by_account(account)
    if not user or user["disabled"] or not verify_password(password, user["password_hash"]):
        return _error("/login", "账号或密码错误", next_url, wants_json, status_code=401)

    _auth_store().mark_login(user["user_id"])
    return _login_response(user, next_url, wants_json)


@router.post("/api/v1/auth/logout")
def logout(request: Request):
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(Settings().auth_cookie_name, path="/")
    return response


@router.get("/api/v1/auth/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return user


async def _read_payload(request: Request) -> tuple[dict, bool]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json(), True
    body = (await request.body()).decode()
    return {k: v[0] for k, v in parse_qs(body).items()}, False


def _login_response(user: dict, next_url: str, wants_json: bool):
    settings = Settings()
    public_user = {"user_id": user["user_id"], "username": user["username"], "email": user["email"], "role": user["role"]}
    response = JSONResponse(public_user) if wants_json else RedirectResponse(next_url, status_code=303)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_auth_token(user["user_id"], settings),
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


def _error(path: str, message: str, next_url: str, wants_json: bool, status_code: int = 400):
    if wants_json:
        return JSONResponse({"detail": message}, status_code=status_code)
    query = urlencode({"next": next_url, "error": message})
    return RedirectResponse(f"{path}?{query}", status_code=303)
