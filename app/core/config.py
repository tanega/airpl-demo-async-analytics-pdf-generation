from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    environment: str = "local"
    db_path: str = "var/db/reports.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
