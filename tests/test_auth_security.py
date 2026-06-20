from unittest.mock import patch

from src.api.auth_security import create_auth_token, read_auth_token
from src.core.config import Settings


def test_auth_session_defaults_to_seven_days():
    assert Settings(_env_file=None).auth_session_hours == 168


def test_auth_token_expires_at_seven_day_boundary():
    settings = Settings(_env_file=None, auth_secret_key="test-secret", auth_session_hours=168)
    issued_at = 1_800_000_000

    with patch("src.api.auth_security.time.time", return_value=issued_at):
        token = create_auth_token("usr-1", settings)

    with patch("src.api.auth_security.time.time", return_value=issued_at + 604_799):
        assert read_auth_token(token, settings) == "usr-1"

    with patch("src.api.auth_security.time.time", return_value=issued_at + 604_800):
        assert read_auth_token(token, settings) is None
