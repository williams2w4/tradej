from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trade Journal"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/tradej"
    default_timezone: str = "America/New_York"
    default_currency: str = "USD"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
