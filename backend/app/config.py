from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# config.py -> app -> backend -> tokenward (where .env lives)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = "tokenward"
    postgres_password: SecretStr
    postgres_db: str = "tokenward"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    # Set to "require" for hosted databases that only accept encrypted connections.
    postgres_sslmode: str | None = None

    # Chat requests each API key may make per minute.
    rate_limit_per_minute: int = Field(default=60, gt=0)

    # Optional. When set, the "gemini-flash" model becomes available.
    gemini_api_key: SecretStr | None = None
    # The upstream Gemini model that "gemini-flash" maps to.
    gemini_model: str = "gemini-3.5-flash-lite"
    # How long to wait for a provider to answer before giving up.
    provider_timeout_seconds: float = Field(default=30.0, gt=0)

    @property
    def database_url(self) -> URL:
        query = {"sslmode": self.postgres_sslmode} if self.postgres_sslmode else {}
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            query=query,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()