from src.api.routes_auth import _login_response


def test_login_cookie_uses_seven_day_max_age(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTH_SESSION_HOURS", "168")

    response = _login_response(
        {"user_id": "usr-1", "username": "alice", "email": "alice@example.com", "role": "user"},
        "/dashboard",
        True,
    )

    cookie = response.headers["set-cookie"]
    assert "Max-Age=604800" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
