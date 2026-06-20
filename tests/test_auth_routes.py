from fastapi.testclient import TestClient

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


def test_registration_never_grants_admin(test_app, monkeypatch):
    created: dict[str, str] = {}

    class FakeAuthStore:
        def get_user_by_account(self, account: str):
            return None

        def create_user(self, username: str, email: str, password_hash: str, role: str):
            created["role"] = role
            return {
                "user_id": "usr-new",
                "username": username,
                "email": email,
                "role": role,
            }

    monkeypatch.setattr("src.api.routes_auth._auth_store", FakeAuthStore)
    client = TestClient(test_app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "tengjiaozhai",
            "email": "admin-attempt@example.com",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )

    assert response.status_code == 200
    assert created["role"] == "user"
