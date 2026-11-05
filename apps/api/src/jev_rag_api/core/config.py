from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_MARKER = "pnpm-workspace.yaml"
JevMode = Literal["mock", "live", "disabled"]


def find_env_file() -> Path | None:
    """Return the repository-root ``.env`` path, or None outside a source checkout."""
    for directory in Path(__file__).resolve().parents:
        if (directory / REPOSITORY_MARKER).is_file():
            return directory / ".env"
    return None


ROOT_ENV_FILE = find_env_file()


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
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:3000"])
    qdrant_url: HttpUrl = HttpUrl("http://127.0.0.1:6333")
    qdrant_timeout_seconds: float = Field(default=1.0, gt=0, allow_inf_nan=False)

    jev_mode: JevMode | None = None
    typesafe_api_key: SecretStr | None = Field(default=None, repr=False)
    typesafe_model: Literal["jev-1.13.0"] = "jev-1.13.0"
    typesafe_timeout_seconds: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    typesafe_retry_max: int = Field(default=1, ge=0)
    typesafe_retry_budget_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)

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
                _ = parts.port
            except ValueError:
                raise ValueError("Invalid CORS origin port") from None
        return origins

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.app_env == "production" and self.app_debug:
            raise ValueError("Debug mode is forbidden in production")
        if self.app_env == "production" and self.jev_mode not in {"live", "disabled"}:
            raise ValueError("Production requires explicit live or disabled Jev mode")
        if self.effective_jev_mode == "live":
            key = self.typesafe_api_key.get_secret_value() if self.typesafe_api_key else ""
            if (
                not key
                or not key.isascii()
                or any(char.isspace() or ord(char) < 33 or ord(char) == 127 for char in key)
            ):
                raise ValueError("Live Jev mode requires a valid API key")
        return self

    @property
    def effective_jev_mode(self) -> JevMode:
        """The configured Jev mode; offline development defaults to the mock adapter."""
        return self.jev_mode or "mock"
