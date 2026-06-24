from src.core.config import Settings


def test_settings_has_llm_timeout():
    s = Settings(llm_timeout=300)
    assert s.llm_timeout == 300


def test_settings_default_llm_timeout():
    s = Settings()
    assert s.llm_timeout == 300


def test_settings_has_research_model():
    s = Settings(llm_model_research="deepseek-v4-pro")
    assert s.llm_model_research == "deepseek-v4-pro"


def test_settings_has_trader_model():
    s = Settings(llm_model_trader="deepseek-v4-flash")
    assert s.llm_model_trader == "deepseek-v4-flash"


def test_settings_default_research_model():
    s = Settings()
    assert s.llm_model_research == "deepseek-v4-pro"


def test_settings_default_trader_model():
    s = Settings()
    assert s.llm_model_trader == "deepseek-v4-flash"
