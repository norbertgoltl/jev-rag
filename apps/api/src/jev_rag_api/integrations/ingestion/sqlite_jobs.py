"""SQLite implementation of ``IngestionJobRepository`` (ING-006).

``attempt`` is the fencing token. A claim increments it. Every later mutation names the attempt it
was claimed under and is applied as a compare-and-swap inside one ``BEGIN IMMEDIATE``
transaction. A stale attempt always raises ``IngestionConflictError`` and changes nothing.

Lease expiry does not invalidate an attempt by itself. Only a newer claim does, so a slow worker
that nobody replaced may still finish. ``release_expired`` plus a new claim is what fences it.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import JobStage, JobStatus
from jev_rag_api.domain.ingestion.errors import (
    ERROR_CODES,
    IngestionConflictError,
    IngestionInvalidStateError,
    IngestionNotFoundError,
)
from jev_rag_api.domain.ingestion.models import IngestionJob
from jev_rag_api.domain.ingestion.transitions import transition_job
from jev_rag_api.integrations.ingestion.sqlite_database import (
    SqliteConnection,
    from_db_time,
    to_db_time,
)

_JOB_COLUMNS = (
    "job_id, job_type, document_id, document_version, index_generation_id, status, stage, "
    "attempt, created_at, updated_at, error_code"
)
_MAX_KEY_LENGTH = 512


def _job_from_row(row: tuple[Any, ...]) -> IngestionJob:
    (
        job_id,
        job_type,
        document_id,
        document_version,
        generation_id,
        status,
        stage,
        attempt,
        created_at,
        updated_at,
        error_code,
    ) = row
    return IngestionJob.model_validate(
        {
            "job_id": job_id,
            "job_type": job_type,
            "document_id": document_id,
            "document_version": document_version,
            "index_generation_id": generation_id,
            "status": status,
            "stage": stage,
            "attempt": attempt,
            "created_at": from_db_time(created_at),
            "updated_at": from_db_time(updated_at),
            "error_code": error_code,
        }
    )


def _load_job(connection: sqlite3.Connection, job_id: UUID) -> IngestionJob:
    row = connection.execute(
        f"SELECT {_JOB_COLUMNS} FROM ingestion_jobs WHERE job_id = ?", (str(job_id),)
    ).fetchone()
    if row is None:
        raise IngestionNotFoundError()
    return _job_from_row(row)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")


def _effective_now(now: datetime, job: IngestionJob) -> datetime:
    """``updated_at`` never moves backwards, even if a caller's clock does."""
    return max(now, job.updated_at)


def _fence(connection: sqlite3.Connection, job_id: UUID, attempt: int) -> IngestionJob:
    """Load the job and verify the caller still owns it.

    Order matters: a stale attempt is a conflict regardless of the job's current status.
    """
    job = _load_job(connection, job_id)
    if attempt != job.attempt:
        raise IngestionConflictError()
    if job.status is not JobStatus.PROCESSING:
        raise IngestionInvalidStateError()
    return job


class SqliteIngestionJobRepository:
    def __init__(self, connection: SqliteConnection) -> None:
        self._connection = connection

    async def enqueue(
        self, job: IngestionJob, *, idempotency_key: str, request_fingerprint: str
    ) -> IngestionJob:
        if (
            not idempotency_key.strip()
            or len(idempotency_key) > _MAX_KEY_LENGTH
            or not request_fingerprint.strip()
            or len(request_fingerprint) > _MAX_KEY_LENGTH
        ):
            raise ValueError("Idempotency key and request fingerprint must be 1-512 characters")
        if job.status is not JobStatus.QUEUED or job.attempt != 0:
            raise IngestionInvalidStateError()

        def work(connection: sqlite3.Connection) -> IngestionJob:
            existing = connection.execute(
                f"SELECT {_JOB_COLUMNS}, request_fingerprint FROM ingestion_jobs "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing[-1] != request_fingerprint:
                    raise IngestionConflictError()
                return _job_from_row(existing[:-1])
            self._require_references(connection, job)
            if connection.execute(
                "SELECT 1 FROM ingestion_jobs WHERE job_id = ?", (str(job.job_id),)
            ).fetchone():
                raise IngestionConflictError()
            connection.execute(
                f"INSERT INTO ingestion_jobs ({_JOB_COLUMNS}, idempotency_key, "
                "request_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(job.job_id),
                    job.job_type.value,
                    str(job.document_id),
                    job.document_version,
                    str(job.index_generation_id) if job.index_generation_id else None,
                    job.status.value,
                    None,
                    job.attempt,
                    to_db_time(job.created_at),
                    to_db_time(job.updated_at),
                    None,
                    idempotency_key,
                    request_fingerprint,
                ),
            )
            return _load_job(connection, job.job_id)

        return await self._connection.run(work)

    @staticmethod
    def _require_references(connection: sqlite3.Connection, job: IngestionJob) -> None:
        if not connection.execute(
            "SELECT 1 FROM documents WHERE document_id = ?", (str(job.document_id),)
        ).fetchone():
            raise IngestionNotFoundError()
        if (
            job.document_version is not None
            and not connection.execute(
                "SELECT 1 FROM document_versions WHERE document_id = ? AND version = ?",
                (str(job.document_id), job.document_version),
            ).fetchone()
        ):
            raise IngestionNotFoundError()
        if (
            job.index_generation_id is not None
            and not connection.execute(
                "SELECT 1 FROM index_generations WHERE generation_id = ? AND document_id = ?",
                (str(job.index_generation_id), str(job.document_id)),
            ).fetchone()
        ):
            raise IngestionNotFoundError()

    async def get(self, job_id: UUID) -> IngestionJob:
        return await self._connection.run(
            lambda connection: _load_job(connection, job_id), write=False
        )

    async def claim(
        self, *, worker_id: str, lease_seconds: int, now: datetime
    ) -> IngestionJob | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("A worker id and a positive lease are required")
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> IngestionJob | None:
            # One processing job per document at a time, oldest queued job first.
            row = connection.execute(
                f"SELECT {_JOB_COLUMNS} FROM ingestion_jobs AS candidate "
                "WHERE status = 'queued' AND updated_at <= ? "
                "AND NOT EXISTS (SELECT 1 FROM ingestion_jobs AS running "
                "WHERE running.document_id = candidate.document_id "
                "AND running.status = 'processing') "
                "ORDER BY created_at, rowid LIMIT 1",
                (to_db_time(now),),
            ).fetchone()
            if row is None:
                return None
            job = _job_from_row(row)
            claimed = transition_job(job, JobStatus.PROCESSING, now=now)
            expires_at = to_db_time(now + timedelta(seconds=lease_seconds))
            cursor = connection.execute(
                "UPDATE ingestion_jobs SET status = 'processing', stage = ?, attempt = ?, "
                "updated_at = ?, error_code = NULL, lease_owner = ?, lease_expires_at = ? "
                "WHERE job_id = ? AND status = 'queued' AND attempt = ?",
                (
                    claimed.stage.value if claimed.stage else None,
                    claimed.attempt,
                    to_db_time(now),
                    worker_id,
                    expires_at,
                    str(job.job_id),
                    job.attempt,
                ),
            )
            if cursor.rowcount != 1:
                raise IngestionConflictError()
            connection.execute(
                "INSERT INTO ingestion_job_attempts (job_id, attempt, worker_id, claimed_at, "
                "lease_expires_at, last_stage) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(job.job_id),
                    claimed.attempt,
                    worker_id,
                    to_db_time(now),
                    expires_at,
                    claimed.stage.value if claimed.stage else None,
                ),
            )
            return _load_job(connection, job.job_id)

        return await self._connection.run(work)

    async def heartbeat(
        self, job_id: UUID, *, attempt: int, lease_seconds: int, now: datetime
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("A positive lease is required")
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> None:
            job = _fence(connection, job_id, attempt)
            expires_at = to_db_time(now + timedelta(seconds=lease_seconds))
            cursor = connection.execute(
                "UPDATE ingestion_jobs SET lease_expires_at = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt = ? AND status = 'processing'",
                (expires_at, to_db_time(_effective_now(now, job)), str(job_id), attempt),
            )
            if cursor.rowcount != 1:
                raise IngestionConflictError()
            connection.execute(
                "UPDATE ingestion_job_attempts SET lease_expires_at = ? "
                "WHERE job_id = ? AND attempt = ?",
                (expires_at, str(job_id), attempt),
            )

        await self._connection.run(work)

    async def record_stage(
        self, job_id: UUID, *, attempt: int, stage: JobStage, now: datetime
    ) -> None:
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> None:
            job = _fence(connection, job_id, attempt)
            cursor = connection.execute(
                "UPDATE ingestion_jobs SET stage = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt = ? AND status = 'processing'",
                (stage.value, to_db_time(_effective_now(now, job)), str(job_id), attempt),
            )
            if cursor.rowcount != 1:
                raise IngestionConflictError()
            connection.execute(
                "UPDATE ingestion_job_attempts SET last_stage = ? WHERE job_id = ? AND attempt = ?",
                (stage.value, str(job_id), attempt),
            )

        await self._connection.run(work)

    async def complete(self, job_id: UUID, *, attempt: int, now: datetime) -> IngestionJob:
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> IngestionJob:
            job = _fence(connection, job_id, attempt)
            stamp = _effective_now(now, job)
            transition_job(job, JobStatus.COMPLETED, now=stamp)
            self._finish(connection, job, "completed", stamp, status="completed", error_code=None)
            return _load_job(connection, job_id)

        return await self._connection.run(work)

    async def fail(
        self, job_id: UUID, *, attempt: int, error_code: str, now: datetime
    ) -> IngestionJob:
        _require_aware(now)
        if error_code not in ERROR_CODES:
            raise IngestionInvalidStateError()

        def work(connection: sqlite3.Connection) -> IngestionJob:
            job = _fence(connection, job_id, attempt)
            stamp = _effective_now(now, job)
            transition_job(job, JobStatus.FAILED, now=stamp, error_code=error_code)
            self._finish(connection, job, "failed", stamp, status="failed", error_code=error_code)
            return _load_job(connection, job_id)

        return await self._connection.run(work)

    @staticmethod
    def _finish(
        connection: sqlite3.Connection,
        job: IngestionJob,
        outcome: str,
        stamp: datetime,
        *,
        status: str,
        error_code: str | None,
    ) -> None:
        keep_stage = status == "failed"
        cursor = connection.execute(
            "UPDATE ingestion_jobs SET status = ?, stage = CASE WHEN ? THEN stage END, "
            "error_code = ?, updated_at = ?, lease_owner = NULL, lease_expires_at = NULL "
            "WHERE job_id = ? AND attempt = ? AND status = 'processing'",
            (status, keep_stage, error_code, to_db_time(stamp), str(job.job_id), job.attempt),
        )
        if cursor.rowcount != 1:
            raise IngestionConflictError()
        connection.execute(
            "UPDATE ingestion_job_attempts SET ended_at = ?, outcome = ?, error_code = ?, "
            "last_stage = COALESCE(?, last_stage) WHERE job_id = ? AND attempt = ?",
            (
                to_db_time(stamp),
                outcome,
                error_code,
                job.stage.value if job.stage else None,
                str(job.job_id),
                job.attempt,
            ),
        )

    async def requeue(self, job_id: UUID, *, now: datetime) -> IngestionJob:
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> IngestionJob:
            job = _load_job(connection, job_id)
            if job.status is not JobStatus.FAILED:
                raise IngestionInvalidStateError()
            stamp = _effective_now(now, job)
            transition_job(job, JobStatus.QUEUED, now=stamp)
            cursor = connection.execute(
                "UPDATE ingestion_jobs SET status = 'queued', stage = NULL, error_code = NULL, "
                "updated_at = ? WHERE job_id = ? AND attempt = ? AND status = 'failed'",
                (to_db_time(stamp), str(job_id), job.attempt),
            )
            if cursor.rowcount != 1:
                raise IngestionConflictError()
            return _load_job(connection, job_id)

        return await self._connection.run(work)

    async def release_expired(self, *, now: datetime) -> tuple[UUID, ...]:
        _require_aware(now)

        def work(connection: sqlite3.Connection) -> tuple[UUID, ...]:
            rows = connection.execute(
                "SELECT job_id, attempt, lease_expires_at FROM ingestion_jobs "
                "WHERE status = 'processing' AND lease_expires_at <= ? "
                "ORDER BY lease_expires_at, rowid",
                (to_db_time(now),),
            ).fetchall()
            released: list[UUID] = []
            for job_id, attempt, lease_expires_at in rows:
                job = _load_job(connection, UUID(job_id))
                stamp = _effective_now(now, job)
                cursor = connection.execute(
                    "UPDATE ingestion_jobs SET status = 'queued', stage = NULL, "
                    "updated_at = ?, lease_owner = NULL, lease_expires_at = NULL "
                    "WHERE job_id = ? AND attempt = ? AND status = 'processing' "
                    "AND lease_expires_at = ?",
                    (to_db_time(stamp), job_id, attempt, lease_expires_at),
                )
                if cursor.rowcount != 1:
                    continue
                connection.execute(
                    "UPDATE ingestion_job_attempts SET ended_at = ?, outcome = 'released', "
                    "last_stage = COALESCE(?, last_stage) WHERE job_id = ? AND attempt = ?",
                    (
                        to_db_time(stamp),
                        job.stage.value if job.stage else None,
                        job_id,
                        attempt,
                    ),
                )
                released.append(UUID(job_id))
            return tuple(released)

        return await self._connection.run(work)
