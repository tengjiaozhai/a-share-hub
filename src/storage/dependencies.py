from functools import lru_cache

from src.core.config import Settings
from src.storage.db import create_runtime_engine
from src.storage.runtime_store import RuntimeStore


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_runtime_store() -> RuntimeStore:
    settings = get_settings()
    engine = create_runtime_engine(settings)
    return RuntimeStore(engine)