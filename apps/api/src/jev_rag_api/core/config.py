from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[5] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:3000"]
    )
    qdrant_url: HttpUrl = HttpUrl("http://127.0.0.1:6333")
    qdrant_timeout_seconds: float = Field(default=1.0, gt=0, allow_inf_nan=False)

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or "*" in origin
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("CORS origins must be explicit HTTP origins")
            try:
                parts.port
            except ValueError:
                raise ValueError("Invalid CORS origin port") from None
        return origins

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.app_env == "production" and self.app_debug:
            raise ValueError("Debug mode is forbidden in production")
        return self
