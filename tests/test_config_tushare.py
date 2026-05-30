from src.core.config import Settings

def test_settings_has_tushare_token():
    settings = Settings()
    assert settings.tushare_token == ""

def test_settings_reads_tushare_token_from_env(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token_123")
    settings = Settings()
    assert settings.tushare_token == "test_token_123"

def test_market_data_provider_defaults_to_auto():
    settings = Settings()
    assert settings.market_data_provider == "auto"
