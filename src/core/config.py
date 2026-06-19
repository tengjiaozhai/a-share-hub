from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"
    app_role: str = "web"
    enable_scheduler: bool = False

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

    auth_secret_key: str = ""
    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = False
    auth_session_hours: int = 168

    broker_hmac_secret: str = ""

    # LLM
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-pro"
    llm_base_url: str = "https://api.deepseek.com"

    # 行情数据源
    market_data_provider: str = "auto"
    tushare_token: str = ""
    tushare_pro_token: str = ""
    
    # 海外服务器代理（通过阿里云跳板访问国内数据源）
    socks_proxy: str = ""

    aws_host: str = "127.0.0.1"
    aws_ssh_user: str = "ec2-user"
    aws_ssh_key_path: Path = Field(default=Path("/path/to/key.pem"))

    # Alpha 执行配置
    alpha_execution_mode: str = "manual"
    alpha_api_base_url: str = ""
    alpha_api_key: str = ""
    alpha_api_secret: str = ""

    # 币安配置
    binance_api_key: str = ""
    binance_api_secret: str = ""

    # 策略配置
    strategy_top_n: int = 10
    strategy_max_position_ratio: float = 0.2
    strategy_buy_score_threshold: float = 0.55
    strategy_sell_score_threshold: float = -0.20
    strategy_scan_buy_threshold_a: float = 0.55
    strategy_scan_buy_threshold_us: float = 0.45
    strategy_min_confirm_bars: int = 61
    strategy_confirm_lookback_days: int = 180
    strategy_lot_size_a: int = 100
    strategy_lot_size_us: int = 1
    strategy_fee_bps: float = 3.0
    strategy_slippage_bps: float = 5.0
    strategy_max_daily_loss_ratio: float = 0.03
