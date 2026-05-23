from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    database_url: str = "postgresql://douya:douya@localhost:5432/douya"
    api_token: str = "change_me"
    enable_live_trading: bool = False
    execution_mode: str = "shadow"
