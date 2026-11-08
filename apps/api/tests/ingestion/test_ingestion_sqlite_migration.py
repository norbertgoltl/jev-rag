import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from registry_support import make_database, raw_db

from jev_rag_api.core.config import Settings
from jev_rag_api.domain.ingestion.errors import IngestionInternalError
from jev_rag_api.integrations.ingestion.local_source_store import LocalSourceDocumentStore
from jev_rag_api.integrations.ingestion.sqlite_database import (
    MIGRATIONS,
    SCHEMA_VERSION,
    SqliteDatabase,
    from_db_time,
    to_db_time,
)
from settings_factory import build_settings

EXPECTED_TABLES = {
    "schema_migrations",
    "documents",
    "document_versions",
    "index_generations",
    "ingestion_jobs",
    "ingestion_job_attempts",
}


def user_tables(path: Path) -> set[str]:
    with raw_db(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {name for (name,) in rows}


def test_sql_01_explicit_init_creates_versioned_schema(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    path = tmp_path / "data" / "registry.sqlite3"
    assert user_tables(path) == EXPECTED_TABLES
    with raw_db(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("SELECT version, name FROM schema_migrations").fetchall() == [
            (MIGRATIONS[0].version, MIGRATIONS[0].name)
        ]
        indexes = {
            name
            for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
    assert {"uq_generations_one_active", "idx_jobs_claim", "idx_jobs_lease"} <= indexes
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    registry_connection = database.connect()
    foreign_keys = registry_connection.run_sync(
        lambda c: c.execute("PRAGMA foreign_keys").fetchone()[0], write=False
    )
    registry_connection.close()
    assert foreign_keys == 1


def test_sql_02_construction_settings_and_import_do_no_io(tmp_path: Path) -> None:
    storage = tmp_path / "data" / "ingestion" / "sources"
    db_path = tmp_path / "data" / "ingestion" / "registry.sqlite3"
    settings = build_settings(
        _env_file=None,
        app_env="test",
        ingestion_storage_root=storage,
        ingestion_db_path=db_path,
    )
    assert isinstance(settings, Settings)
    SqliteDatabase(db_path)
    LocalSourceDocumentStore(storage, max_file_bytes=settings.ingestion_max_file_bytes)
    assert list(tmp_path.iterdir()) == []

    script = (
        "import jev_rag_api.main, jev_rag_api.integrations.ingestion.sqlite_jobs, "
        "jev_rag_api.integrations.ingestion.sqlite_documents, "
        "jev_rag_api.integrations.ingestion.local_source_store, "
        "jev_rag_api.integrations.ingestion.content_validation"
    )
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    subprocess.run([sys.executable, "-I", "-c", script], cwd=workdir, check=True)
    assert list(workdir.iterdir()) == []
    assert not (tmp_path / "data").exists()


def test_mig_01_repeated_initialization_keeps_data(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    path = tmp_path / "data" / "registry.sqlite3"
    with raw_db(path) as connection:
        connection.execute(
            "INSERT INTO documents (document_id, created_at) VALUES (?, ?)",
            (
                "0" * 8 + "-0000-4000-8000-" + "0" * 12,
                to_db_time(from_db_time("2026-01-01T00:00:00.000000Z")),
            ),
        )
    database.initialize()
    SqliteDatabase(path).initialize()
    with raw_db(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_mig_02_newer_schema_fails_fast_without_modification(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite3"
    with raw_db(path) as connection:
        connection.execute("CREATE TABLE future (x INTEGER)")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    before = path.read_bytes()
    database = SqliteDatabase(path)
    with pytest.raises(IngestionInternalError):
        database.initialize()
    with pytest.raises(IngestionInternalError):
        database.connect()
    assert path.read_bytes() == before
    assert not Path(f"{path}-wal").exists()
    assert user_tables(path) == {"future"}


def test_foreign_unversioned_database_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite3"
    with raw_db(path) as connection:
        connection.execute("CREATE TABLE unrelated (x INTEGER)")
    with pytest.raises(IngestionInternalError):
        SqliteDatabase(path).initialize()
    assert user_tables(path) == {"unrelated"}


def test_corrupt_database_file_is_rejected_with_a_domain_error(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite3"
    path.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises(IngestionInternalError) as caught:
        SqliteDatabase(path).initialize()
    assert str(tmp_path) not in repr(caught.value)


def test_inconsistent_migration_history_is_rejected(tmp_path: Path) -> None:
    make_database(tmp_path)
    path = tmp_path / "data" / "registry.sqlite3"
    with raw_db(path) as connection:
        connection.execute("DELETE FROM schema_migrations")
    with pytest.raises(IngestionInternalError):
        SqliteDatabase(path).initialize()


def test_connect_requires_an_initialized_database(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "registry.sqlite3"
    with pytest.raises(IngestionInternalError):
        SqliteDatabase(path).connect()
    assert not path.parent.exists()

    empty = tmp_path / "empty.sqlite3"
    sqlite3.connect(empty).close()
    with pytest.raises(IngestionInternalError):
        SqliteDatabase(empty).connect()


def test_symlinked_database_path_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real.sqlite3"
    real.touch()
    link = tmp_path / "link.sqlite3"
    link.symlink_to(real)
    with pytest.raises(IngestionInternalError):
        SqliteDatabase(link).initialize()


def test_busy_timeout_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        SqliteDatabase(tmp_path / "x.sqlite3", busy_timeout_ms=0)


def test_timestamp_helpers_round_trip_and_reject_naive_values() -> None:
    from datetime import datetime

    value = from_db_time("2026-03-01T12:00:00.123456Z")
    assert to_db_time(value) == "2026-03-01T12:00:00.123456Z"
    with pytest.raises(ValueError, match="timezone-aware"):
        to_db_time(datetime(2026, 1, 1))


def test_schema_enforces_foreign_keys_and_constraints(tmp_path: Path) -> None:
    make_database(tmp_path)
    path = tmp_path / "data" / "registry.sqlite3"
    with raw_db(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO document_versions VALUES (?, 1, ?, 'a.txt', 'text/plain', 'k', 'x')",
                ("1" * 36, "a" * 64),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO documents (document_id, created_at, active_version) "
                "VALUES (?, 'x', 1)",
                ("2" * 36,),
            )
