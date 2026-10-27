from pathlib import Path

import pytest
from pydantic import ValidationError

from jev_rag_api.core.config import ROOT_ENV_FILE, Settings


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
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_defaults_without_dotenv(tmp_path):
    config = Settings(_env_file=tmp_path / "missing.env")
    assert config.api_host == "127.0.0.1"
    assert config.api_port == 8000
    assert config.qdrant_timeout_seconds == 1


def test_source_priority_and_unknown_dotenv_keys(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("API_PORT=8100\nCOMPOSE_ONLY=value\n")
    assert Settings(_env_file=env_file).api_port == 8100
    monkeypatch.setenv("API_PORT", "8200")
    assert Settings(_env_file=env_file).api_port == 8200
    assert Settings(_env_file=env_file, api_port=8300).api_port == 8300


def test_origin_json_environment(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://example.com"]')
    assert Settings(_env_file=None).cors_allowed_origins == ["https://example.com"]


def test_dotenv_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    assert ROOT_ENV_FILE.is_absolute()
    assert ROOT_ENV_FILE == Path(__file__).resolve().parents[3] / ".env"
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == ROOT_ENV_FILE


def test_settings_errors_do_not_include_input():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, api_port="secret-value")
    assert "secret-value" not in str(error.value)
