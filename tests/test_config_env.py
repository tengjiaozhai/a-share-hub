from src.core.config import Settings


def test_settings_expose_alpha_execution_configuration(monkeypatch):
    monkeypatch.setenv("ALPHA_EXECUTION_MODE", "api")
    monkeypatch.setenv("ALPHA_API_BASE_URL", "https://example.binance.test")
    monkeypatch.setenv("ALPHA_API_KEY", "key-123")
    monkeypatch.setenv("ALPHA_API_SECRET", "secret-123")

    settings = Settings()

    assert settings.alpha_execution_mode == "api"
    assert settings.alpha_api_base_url == "https://example.binance.test"
    assert settings.alpha_api_key == "key-123"
    assert settings.alpha_api_secret == "secret-123"
