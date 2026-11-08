"""SQLite connection lifecycle, versioned migrations, and error mapping (ING-006).

Nothing here runs at import time. ``SqliteDatabase.initialize`` is the only operation that
creates directories, the database file, or the schema. Repositories use ``SqliteConnection``,
which serializes use of one ``sqlite3`` connection with a lock and runs every unit of work in
one explicit transaction. Cross-connection and cross-process safety comes from SQLite itself
(``BEGIN IMMEDIATE``, constraints, ``busy_timeout``), not from the process-local lock.
"""

import asyncio
import os
import sqlite3
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from jev_rag_api.domain.ingestion.enums import IndexGenerationState, JobStage, JobStatus, JobType
from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionError,
    IngestionInternalError,
)

DEFAULT_BUSY_TIMEOUT_MS = 5_000
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


def to_db_time(value: datetime) -> str:
    """Fixed-width UTC text so lexicographic order equals chronological order."""
    if value.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value.astimezone(UTC).strftime(_TIMESTAMP_FORMAT)


def from_db_time(value: str) -> datetime:
    return datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def _in_list(values: list[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_GENERATION_STATES = _in_list([state.value for state in IndexGenerationState])
_JOB_STATUSES = _in_list([status.value for status in JobStatus])
_JOB_STAGES = _in_list([stage.value for stage in JobStage])
_JOB_TYPES = _in_list([job_type.value for job_type in JobType])


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


# Migrations are append-only. Editing a released migration is a contract change.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="initial_ingestion_registry",
        statements=(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            ) STRICT
            """,
            """
            CREATE TABLE documents (
                document_id TEXT PRIMARY KEY CHECK (length(document_id) = 36),
                created_at TEXT NOT NULL,
                active_version INTEGER,
                active_generation_id TEXT,
                deleted_at TEXT,
                CHECK ((active_version IS NULL) = (active_generation_id IS NULL)),
                CHECK (deleted_at IS NULL OR active_version IS NULL),
                FOREIGN KEY (document_id, active_version)
                    REFERENCES document_versions (document_id, version),
                FOREIGN KEY (active_generation_id, document_id, active_version)
                    REFERENCES index_generations (generation_id, document_id, document_version)
            ) STRICT
            """,
            """
            CREATE TABLE document_versions (
                document_id TEXT NOT NULL REFERENCES documents (document_id),
                version INTEGER NOT NULL CHECK (version >= 1),
                content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
                source_name TEXT NOT NULL CHECK (length(source_name) BETWEEN 1 AND 255),
                media_type TEXT NOT NULL CHECK (length(media_type) BETWEEN 3 AND 255),
                storage_key TEXT NOT NULL UNIQUE CHECK (length(storage_key) BETWEEN 1 AND 512),
                created_at TEXT NOT NULL,
                PRIMARY KEY (document_id, version)
            ) STRICT
            """,
            f"""
            CREATE TABLE index_generations (
                generation_id TEXT PRIMARY KEY CHECK (length(generation_id) = 36),
                document_id TEXT NOT NULL,
                document_version INTEGER NOT NULL CHECK (document_version >= 1),
                pipeline_fingerprint TEXT NOT NULL CHECK (length(pipeline_fingerprint) = 64),
                state TEXT NOT NULL CHECK (state IN ({_GENERATION_STATES})),
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id, document_version)
                    REFERENCES document_versions (document_id, version),
                UNIQUE (generation_id, document_id),
                UNIQUE (generation_id, document_id, document_version)
            ) STRICT
            """,
            "CREATE INDEX idx_generations_document ON index_generations (document_id, state)",
            """
            CREATE UNIQUE INDEX uq_generations_one_active
                ON index_generations (document_id) WHERE state = 'active'
            """,
            f"""
            CREATE TABLE ingestion_jobs (
                job_id TEXT PRIMARY KEY CHECK (length(job_id) = 36),
                job_type TEXT NOT NULL CHECK (job_type IN ({_JOB_TYPES})),
                document_id TEXT NOT NULL REFERENCES documents (document_id),
                document_version INTEGER CHECK (document_version >= 1),
                index_generation_id TEXT,
                status TEXT NOT NULL CHECK (status IN ({_JOB_STATUSES})),
                stage TEXT CHECK (stage IS NULL OR stage IN ({_JOB_STAGES})),
                attempt INTEGER NOT NULL CHECK (attempt >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) > 0),
                request_fingerprint TEXT NOT NULL CHECK (length(request_fingerprint) > 0),
                lease_owner TEXT,
                lease_expires_at TEXT,
                CHECK (updated_at >= created_at),
                CHECK (job_type = 'delete' OR document_version IS NOT NULL),
                CHECK ((status = 'processing') = (stage IS NOT NULL) OR status = 'failed'),
                CHECK (status <> 'queued' OR stage IS NULL),
                CHECK (status <> 'completed' OR stage IS NULL),
                CHECK (status = 'queued' OR attempt >= 1),
                CHECK ((status = 'failed') = (error_code IS NOT NULL)),
                CHECK ((status = 'processing') = (lease_owner IS NOT NULL)),
                CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
                FOREIGN KEY (document_id, document_version)
                    REFERENCES document_versions (document_id, version),
                FOREIGN KEY (index_generation_id, document_id)
                    REFERENCES index_generations (generation_id, document_id)
            ) STRICT
            """,
            "CREATE INDEX idx_jobs_claim ON ingestion_jobs (status, created_at)",
            "CREATE INDEX idx_jobs_lease ON ingestion_jobs (status, lease_expires_at)",
            "CREATE INDEX idx_jobs_document ON ingestion_jobs (document_id, status)",
            """
            CREATE TABLE ingestion_job_attempts (
                job_id TEXT NOT NULL REFERENCES ingestion_jobs (job_id),
                attempt INTEGER NOT NULL CHECK (attempt >= 1),
                worker_id TEXT NOT NULL CHECK (length(worker_id) > 0),
                claimed_at TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                last_stage TEXT,
                ended_at TEXT,
                outcome TEXT
                    CHECK (outcome IS NULL OR outcome IN ('completed', 'failed', 'released')),
                error_code TEXT,
                PRIMARY KEY (job_id, attempt),
                CHECK ((ended_at IS NULL) = (outcome IS NULL))
            ) STRICT
            """,
        ),
    ),
)
SCHEMA_VERSION = MIGRATIONS[-1].version


def map_database_error(error: BaseException) -> IngestionError:
    """Translate driver and validation failures. Messages and paths are never carried over."""
    if isinstance(error, IngestionError):
        return error
    if isinstance(error, sqlite3.IntegrityError):
        return IngestionConflictError()
    return IngestionInternalError()


class SqliteConnection:
    """One SQLite connection used from async code through worker threads."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        self._closed = False

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._connection.close()

    async def run[T](self, work: Callable[[sqlite3.Connection], T], *, write: bool = True) -> T:
        """Run ``work`` in one transaction. Roll back on any failure."""
        return await asyncio.to_thread(self.run_sync, work, write=write)

    def run_sync[T](self, work: Callable[[sqlite3.Connection], T], *, write: bool = True) -> T:
        with self._lock:
            if self._closed:
                raise IngestionInternalError()
            connection = self._connection
            try:
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            except sqlite3.Error as error:
                raise map_database_error(error) from None
            try:
                result = work(connection)
                connection.execute("COMMIT")
                return result
            except BaseException as error:
                self._rollback(connection)
                if isinstance(error, IngestionError):
                    raise
                if isinstance(error, sqlite3.Error | ValidationError):
                    raise map_database_error(error) from None
                raise

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass


class SqliteDatabase:
    """Locates, creates, and opens the registry database. Construction performs no I/O."""

    def __init__(self, path: Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self._path = path
        self._busy_timeout_ms = busy_timeout_ms

    def initialize(self) -> None:
        """Create the directory and file when missing, then apply pending migrations.

        Repeatable. Fails fast on a newer schema, a foreign database, or a damaged file.
        """
        try:
            self._prepare_file()
            connection = self._open(create=True)
        except OSError, sqlite3.Error:
            raise IngestionInternalError() from None
        try:
            self._migrate(connection)
        except IngestionError:
            raise
        except sqlite3.Error, ValidationError:
            raise IngestionInternalError() from None
        finally:
            connection.close()

    def connect(self) -> SqliteConnection:
        """Open a new connection to an initialized database. Never creates or migrates."""
        try:
            connection = self._open(create=False)
        except OSError, sqlite3.Error:
            raise IngestionInternalError() from None
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.Error:
            connection.close()
            raise IngestionInternalError() from None
        if version != SCHEMA_VERSION:
            connection.close()
            raise IngestionInternalError()
        return SqliteConnection(connection)

    def _prepare_file(self) -> None:
        directory = self._path.parent
        directory.mkdir(mode=_DIRECTORY_MODE, parents=True, exist_ok=True)
        if self._path.is_symlink():
            raise OSError("The database path must not be a symbolic link")
        descriptor = os.open(
            self._path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, _FILE_MODE
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("The database path must be a regular file")
        finally:
            os.close(descriptor)

    def _open(self, *, create: bool) -> sqlite3.Connection:
        mode = "rwc" if create else "rw"
        connection = sqlite3.connect(
            f"{self._path.resolve().as_uri()}?mode={mode}",
            uri=True,
            isolation_level=None,
            check_same_thread=False,
            timeout=self._busy_timeout_ms / 1000,
        )
        try:
            connection.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise sqlite3.OperationalError("foreign keys unavailable")
            connection.execute("PRAGMA trusted_schema = OFF")
        except BaseException:
            connection.close()
            raise
        return connection

    def _migrate(self, connection: sqlite3.Connection) -> None:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise IngestionInternalError()
        # Rejected before any write so a newer or foreign database is left untouched.
        self._check_upgradable(connection)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = self._check_upgradable(connection)
            if current > 0:
                self._verify_history(connection, current)
            for migration in MIGRATIONS:
                if migration.version <= current:
                    continue
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.name, to_db_time(datetime.now(UTC))),
                )
                connection.execute(f"PRAGMA user_version = {int(migration.version)}")
            connection.execute("COMMIT")
        except BaseException:
            SqliteConnection._rollback(connection)
            raise

    @staticmethod
    def _check_upgradable(connection: sqlite3.Connection) -> int:
        current: int = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise IngestionInternalError()
        if current == 0 and connection.execute("SELECT 1 FROM sqlite_master").fetchone():
            # A database with objects but no version was not created by this adapter.
            raise IngestionInternalError()
        return current

    @staticmethod
    def _verify_history(connection: sqlite3.Connection, version: int) -> None:
        recorded = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if recorded != version:
            raise IngestionInternalError()
