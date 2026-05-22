import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_INSECURE_DEFAULTS = {
    "dev-secret-change-in-production",
    "change-me-to-a-long-random-string",
    "changeme",
    "secret",
    "",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str = "redis://localhost:6379"
    # No default — must be set explicitly in .env / environment.
    # In production use a long random string (e.g. `openssl rand -hex 32`).
    secret_key: str
    environment: str = "development"
    log_level: str = "INFO"

    webhook_worker_poll_interval: int = 5
    webhook_max_attempts: int = 5

    @field_validator("secret_key")
    @classmethod
    def _warn_insecure_secret(cls, v: str) -> str:
        if v in _INSECURE_DEFAULTS:
            raise ValueError(
                "SECRET_KEY is set to an insecure placeholder. "
                "Set a strong random value in .env (e.g. `openssl rand -hex 32`)."
            )
        return v


settings = Settings()
