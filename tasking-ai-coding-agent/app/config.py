from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-5"

    # Database
    database_url: str = "sqlite+aiosqlite:///./tasking.db"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # GitHub
    github_token: str = ""
    github_repo: str = ""

    # Sandbox
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout: int = 30

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
