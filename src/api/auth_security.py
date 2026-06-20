import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.core.config import Settings
from src.storage.auth_store import AuthStore
from src.storage.dependencies import get_runtime_engine

PUBLIC_EXACT = {
    "/login",
    "/register",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/health",
    "/health",
}
PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(digest, expected)


def create_auth_token(user_id: str, settings: Settings) -> str:
    payload = _b64encode_json({"uid": user_id, "exp": int(time.time()) + settings.auth_session_hours * 3600})
    return f"{payload}.{_sign(payload, settings)}"


def read_auth_token(token: str, settings: Settings) -> str | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload, settings), signature):
        return None
    try:
        data = _b64decode_json(payload)
    except Exception:
        return None
    if int(data.get("exp", 0)) <= int(time.time()):
        return None
    return str(data.get("uid") or "") or None


def get_current_user_from_request(request: Request) -> dict | None:
    settings = Settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    user_id = read_auth_token(token, settings)
    if not user_id:
        return None
    user = AuthStore(get_runtime_engine()).get_user(user_id)
    if not user or user["disabled"]:
        return None
    return _public_user(user)


async def auth_middleware(request: Request, call_next):
    user = get_current_user_from_request(request)
    request.state.user = user

    if request.url.path in {"/login", "/register"} and user:
        return RedirectResponse("/dashboard", status_code=303)

    if request.url.path == "/dashboard" and not user:
        return RedirectResponse("/login?next=/dashboard", status_code=303)

    return await call_next(request)


def _public_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
    }


def require_role(*allowed_roles: str):
    """FastAPI 依赖：要求当前用户拥有指定角色之一。"""

    async def _checker(request: Request) -> dict[str, object]:
        user = request.state.user
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        if allowed_roles and user.get("role") not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _checker


def verify_broker_signature(
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    secret: str,
    max_skew_seconds: int = 300,
) -> bool:
    """校验券商回调 HMAC 签名。

    约定：
    - Header `X-Broker-Timestamp`：Unix 秒级时间戳
    - Header `X-Broker-Signature`：hex(HMAC-SHA256(secret, f"{timestamp}.{body}"))
    - 时间戳偏差超过 max_skew_seconds 视为重放
    """

    if not signature or not timestamp:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if abs(now - ts) > max_skew_seconds:
        return False
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)


def _secret(settings: Settings) -> str:
    return settings.auth_secret_key or settings.api_token


def _sign(payload: str, settings: Settings) -> str:
    digest = hmac.new(_secret(settings).encode(), payload.encode(), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode())


def _b64encode_json(data: dict) -> str:
    return _b64encode(json.dumps(data, separators=(",", ":")).encode())


def _b64decode_json(value: str) -> dict:
    return json.loads(_b64decode(value).decode())
