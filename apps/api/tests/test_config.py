from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from jev_rag_api.core.config import ROOT_ENV_FILE, Settings, find_env_file
from settings_factory import build_settings


@pytest.mark.parametrize(
    "values",
    [
        {"api_port": 0},
        {"api_port": 65536},
        {"api_port": "invalid"},
        {"qdrant_url": "not-a-url"},
        {"qdrant_url": "ftp://localhost"},
        {"qdrant_timeout_seconds": -1},
        {"qdrant_timeout_seconds": float("inf")},
        {"app_env": "invalid"},
        {"log_level": "invalid"},
        {"app_env": "production", "app_debug": True},
        {"cors_allowed_origins": ["*"]},
        {"cors_allowed_origins": ["https://example.com/path"]},
    ],
)
def test_invalid_settings(values: Any) -> None:
    with pytest.raises(ValidationError):
        build_settings(_env_file=None, **values)


def test_defaults_without_dotenv(tmp_path: Path) -> None:
    config = build_settings(_env_file=tmp_path / "missing.env")
    assert config.api_host == "127.0.0.1"
    assert config.api_port == 8000
    assert config.qdrant_timeout_seconds == 1


def test_source_priority_and_unknown_dotenv_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("API_PORT=8100\nCOMPOSE_ONLY=value\n")
    assert build_settings(_env_file=env_file).api_port == 8100
    monkeypatch.setenv("API_PORT", "8200")
    assert build_settings(_env_file=env_file).api_port == 8200
    assert build_settings(_env_file=env_file, api_port=8300).api_port == 8300


def test_origin_json_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://example.com"]')
    assert build_settings(_env_file=None).cors_allowed_origins == ["https://example.com"]


def test_dotenv_path_is_independent_of_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ROOT_ENV_FILE is not None and ROOT_ENV_FILE.is_absolute()
    assert ROOT_ENV_FILE == Path(__file__).resolve().parents[3] / ".env"
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == ROOT_ENV_FILE


def test_settings_errors_do_not_include_input() -> None:
    with pytest.raises(ValidationError) as error:
        build_settings(_env_file=None, api_port="secret-value")
    assert "secret-value" not in str(error.value)


def test_find_env_file_is_none_outside_a_source_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jev_rag_api.core.config.REPOSITORY_MARKER", "no-such-marker.yaml")
    assert find_env_file() is None


def test_unset_jev_mode_defaults_to_mock_without_mutating_settings() -> None:
    config = build_settings()
    assert config.jev_mode is None
    assert config.effective_jev_mode == "mock"


def test_explicit_jev_mode_is_effective() -> None:
    assert build_settings(jev_mode="disabled").effective_jev_mode == "disabled"
