import re
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
REPOSITORY_ROOT = ROOT_ENV_FILE.parent if ROOT_ENV_FILE else None

SUPPORTED_INGESTION_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx"})
COLLECTION_NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,62}")
EmbeddingProviderName = Literal["none"]


def _default_ingestion_path(*parts: str) -> Path | None:
    return REPOSITORY_ROOT.joinpath(*parts) if REPOSITORY_ROOT else None


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

    ingestion_enabled: bool = False
    ingestion_storage_root: Path | None = Field(
        default_factory=lambda: _default_ingestion_path("data", "ingestion", "sources")
    )
    ingestion_db_path: Path | None = Field(
        default_factory=lambda: _default_ingestion_path("data", "ingestion", "registry.sqlite3")
    )
    ingestion_max_file_bytes: int = Field(default=26_214_400, gt=0)
    ingestion_allowed_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".md", ".pdf", ".docx"]
    )
    ingestion_max_concurrent_jobs: int = Field(default=1, gt=0)
    ingestion_job_lease_seconds: int = Field(default=300, gt=0)
    ingestion_chunk_target_tokens: int = Field(default=400, gt=0)
    ingestion_chunk_overlap_tokens: int = Field(default=64, ge=0)
    ingestion_embedding_provider: EmbeddingProviderName = "none"
    ingestion_embedding_model: str | None = None
    ingestion_embedding_batch_size: int = Field(default=16, gt=0)
    ingestion_qdrant_collection: str = "rag_chunks_v1"
    ingestion_allow_remote_embedding: bool = False

    @field_validator("ingestion_storage_root", "ingestion_db_path")
    @classmethod
    def normalize_ingestion_path(cls, path: Path | None) -> Path | None:
        """Resolve relative values against the repository root, never the working directory."""
        if path is None or path.is_absolute():
            return path
        if REPOSITORY_ROOT is None:
            raise ValueError("Ingestion paths must be absolute outside a source checkout")
        return REPOSITORY_ROOT / path

    @field_validator("ingestion_allowed_extensions")
    @classmethod
    def validate_extensions(cls, extensions: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(extension.strip().lower() for extension in extensions))
        if not normalized or not set(normalized) <= SUPPORTED_INGESTION_EXTENSIONS:
            raise ValueError("Allowed extensions must be a non-empty supported subset")
        return normalized

    @field_validator("ingestion_embedding_model")
    @classmethod
    def validate_embedding_model(cls, model: str | None) -> str | None:
        if model is not None and not model.strip():
            raise ValueError("Embedding model must not be blank")
        return model.strip() if model else None

    @field_validator("ingestion_qdrant_collection")
    @classmethod
    def validate_collection_name(cls, name: str) -> str:
        if not COLLECTION_NAME_PATTERN.fullmatch(name):
            raise ValueError("Invalid Qdrant collection name")
        return name

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
        if self.ingestion_chunk_overlap_tokens >= self.ingestion_chunk_target_tokens:
            raise ValueError("Chunk overlap must be lower than the chunk target")
        if self.ingestion_enabled and (
            self.ingestion_embedding_provider == "none"
            or self.ingestion_embedding_model is None
            or self.ingestion_storage_root is None
            or self.ingestion_db_path is None
        ):
            raise ValueError("Enabled ingestion requires a provider, a model, and storage paths")
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
