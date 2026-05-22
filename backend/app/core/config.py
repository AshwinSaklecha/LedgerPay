from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://ledgerpay:ledgerpay@localhost:5433/ledgerpay"
    redis_url: str = "redis://localhost:6380"
    secret_key: str = "dev-secret-change-in-production"
    environment: str = "development"
    log_level: str = "INFO"

    webhook_worker_poll_interval: int = 5
    webhook_max_attempts: int = 5


settings = Settings()
