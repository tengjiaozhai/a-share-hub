import os
from pathlib import Path
from src.core.config import Settings

def test_runtime_store_path_default():
    settings = Settings()
    expected = Path.home() / ".a-share-hub" / "runtime_store"
    assert settings.runtime_store_path == expected

def test_runtime_store_path_from_env(monkeypatch):
    monkeypatch.setenv("RUNTIME_STORE_PATH", "/tmp/test_store")
    settings = Settings()
    assert settings.runtime_store_path == Path("/tmp/test_store")