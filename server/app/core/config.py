from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def reject_placeholder_password(self) -> "Settings":
        password = self.postgres_password.get_secret_value()
        if not password or password.startswith("replace-with-"):
            raise ValueError("Set a unique POSTGRES_PASSWORD in .env before starting the API")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
