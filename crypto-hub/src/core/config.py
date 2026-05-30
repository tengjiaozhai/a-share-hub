from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional
import os

class BinanceConfig(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    api_key: str = Field("test_api_key", validation_alias="BINANCE_API_KEY")
    api_secret: str = Field("test_api_secret", validation_alias="BINANCE_API_SECRET")
    testnet: bool = Field(True, validation_alias="BINANCE_TESTNET")

class TradingConfig(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    enabled: bool = Field(True, validation_alias="CRYPTO_ENABLED")
    max_position_ratio: float = Field(0.1, validation_alias="CRYPTO_MAX_POSITION_RATIO")
    max_daily_loss: float = Field(0.05, validation_alias="CRYPTO_MAX_DAILY_LOSS")
    min_liquidity: float = Field(1000000, validation_alias="CRYPTO_MIN_LIQUIDITY")
    stop_loss_ratio: float = Field(0.02, validation_alias="CRYPTO_STOP_LOSS_RATIO")

class Config:
    def __init__(self):
        self.binance = BinanceConfig()
        self.trading = TradingConfig()