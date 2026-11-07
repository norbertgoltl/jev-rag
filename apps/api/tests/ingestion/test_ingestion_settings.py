from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from jev_rag_api.core.config import REPOSITORY_ROOT, Settings
from settings_factory import build_settings


def test_ingestion_defaults_without_dotenv() -> None:
    config = build_settings(_env_file=None)
    assert config.ingestion_enabled is False
    assert config.ingestion_max_file_bytes == 26_214_400
    assert config.ingestion_allowed_extensions == [".txt", ".md", ".pdf", ".docx"]
    assert config.ingestion_max_concurrent_jobs == 1
    assert config.ingestion_job_lease_seconds == 300
    assert config.ingestion_chunk_target_tokens == 400
    assert config.ingestion_chunk_overlap_tokens == 64
    assert config.ingestion_embedding_provider == "none"
    assert config.ingestion_embedding_model is None
    assert config.ingestion_embedding_batch_size == 16
    assert config.ingestion_qdrant_collection == "rag_chunks_v1"
    assert config.ingestion_allow_remote_embedding is False
    assert REPOSITORY_ROOT is not None
    assert config.ingestion_storage_root == REPOSITORY_ROOT / "data/ingestion/sources"
    assert config.ingestion_db_path == REPOSITORY_ROOT / "data/ingestion/registry.sqlite3"


def test_settings_creation_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    root = tmp_path / "store"
    build_settings(_env_file=None, ingestion_storage_root=root, ingestion_db_path=tmp_path / "db")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "values",
    [
        {"ingestion_max_file_bytes": 0},
        {"ingestion_max_file_bytes": -1},
        {"ingestion_max_concurrent_jobs": 0},
        {"ingestion_job_lease_seconds": 0},
        {"ingestion_chunk_target_tokens": 0},
        {"ingestion_chunk_overlap_tokens": -1},
        {"ingestion_chunk_overlap_tokens": 400},
        {"ingestion_chunk_target_tokens": 50, "ingestion_chunk_overlap_tokens": 64},
        {"ingestion_embedding_batch_size": 0},
        {"ingestion_qdrant_collection": ""},
        {"ingestion_qdrant_collection": "../etc"},
        {"ingestion_qdrant_collection": "1bad"},
        {"ingestion_qdrant_collection": "a" * 64},
        {"ingestion_allowed_extensions": []},
        {"ingestion_allowed_extensions": [".exe"]},
        {"ingestion_embedding_model": "   "},
        {"ingestion_embedding_provider": "remote"},
        {"ingestion_enabled": True},
        {"ingestion_enabled": True, "ingestion_embedding_model": "m"},
    ],
)
def test_invalid_ingestion_settings(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        build_settings(_env_file=None, **values)


def test_extensions_are_normalized() -> None:
    config = build_settings(_env_file=None, ingestion_allowed_extensions=[".PDF", ".pdf", ".Txt"])
    assert config.ingestion_allowed_extensions == [".pdf", ".txt"]


def test_relative_paths_resolve_against_repository_root_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = build_settings(_env_file=None, ingestion_db_path="custom/registry.sqlite3")
    assert REPOSITORY_ROOT is not None
    assert config.ingestion_db_path == REPOSITORY_ROOT / "custom/registry.sqlite3"


def test_environment_overrides_dotenv_and_unknown_keys_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'INGESTION_MAX_FILE_BYTES=100\nINGESTION_ALLOWED_EXTENSIONS=[".md"]\nOTHER_COMPONENT=x\n'
    )
    config = build_settings(_env_file=env_file)
    assert config.ingestion_max_file_bytes == 100
    assert config.ingestion_allowed_extensions == [".md"]
    monkeypatch.setenv("INGESTION_MAX_FILE_BYTES", "200")
    assert build_settings(_env_file=env_file).ingestion_max_file_bytes == 200


def test_validation_errors_do_not_echo_input() -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(_env_file=None, ingestion_embedding_model="  ")
    assert "input_value" not in str(caught.value)


def test_all_ingestion_fields_are_documented_in_env_example() -> None:
    example = (REPOSITORY_ROOT / ".env.example").read_text() if REPOSITORY_ROOT else ""
    for name in Settings.model_fields:
        if name.startswith("ingestion_"):
            assert name.upper() in example
