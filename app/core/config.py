from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Relink API"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://relink:relink@db:5432/relink"
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    jwt_secret_key: str = "change_me"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60 * 24

    cache_ttl_seconds: int = 3600
    cleanup_interval_sec: int = 60
    inactive_days: int = 30


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
