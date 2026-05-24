from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 30
    db_echo: bool = False

    redis_enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_role: str = "none"
    redis_maxmemory_mb: int = 128
    redis_kill_switch_ttl_seconds: int = 1
    redis_ready_plan_ttl_seconds: int = 5

    api_token: str = "change_me"
    enable_live_trading: bool = False
    execution_mode: str = "shadow"

    aws_host: str = "127.0.0.1"
    aws_ssh_user: str = "ec2-user"
    aws_ssh_key_path: Path = Field(default=Path("/path/to/key.pem"))
