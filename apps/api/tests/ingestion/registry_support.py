import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from jev_rag_api.domain.ingestion.enums import IndexGenerationState, JobStatus, JobType
from jev_rag_api.domain.ingestion.models import (
    DocumentRecord,
    DocumentVersion,
    IndexGeneration,
    IngestionJob,
)
from jev_rag_api.integrations.ingestion.sqlite_database import SqliteConnection, SqliteDatabase
from jev_rag_api.integrations.ingestion.sqlite_documents import SqliteDocumentRepository
from jev_rag_api.integrations.ingestion.sqlite_jobs import SqliteIngestionJobRepository

T0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
SHA = "a" * 64
FINGERPRINT = "b" * 64


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def make_database(directory: Path) -> SqliteDatabase:
    database = SqliteDatabase(directory / "data" / "registry.sqlite3")
    database.initialize()
    return database


def make_record(document_id: UUID | None = None, *, created_at: datetime = T0) -> DocumentRecord:
    return DocumentRecord(document_id=document_id or uuid4(), created_at=created_at)


def make_version(
    document_id: UUID, version: int = 1, *, storage_key: str | None = None, sha: str = SHA
) -> DocumentVersion:
    return DocumentVersion(
        document_id=document_id,
        version=version,
        content_sha256=sha,
        source_name="guide.pdf",
        media_type="application/pdf",
        storage_key=storage_key or f"ab/{uuid4().hex}",
        created_at=T0,
    )


def make_generation(
    document_id: UUID,
    version: int = 1,
    *,
    state: IndexGenerationState = IndexGenerationState.STAGED,
) -> IndexGeneration:
    return IndexGeneration(
        generation_id=uuid4(),
        document_id=document_id,
        document_version=version,
        pipeline_fingerprint=FINGERPRINT,
        state=state,
        created_at=T0,
    )


def make_queued_job(
    document_id: UUID,
    *,
    version: int | None = 1,
    created_at: datetime = T0,
    job_type: JobType = JobType.INGEST,
    generation_id: UUID | None = None,
) -> IngestionJob:
    return IngestionJob(
        job_id=uuid4(),
        job_type=job_type,
        document_id=document_id,
        document_version=version,
        index_generation_id=generation_id,
        status=JobStatus.QUEUED,
        attempt=0,
        created_at=created_at,
        updated_at=created_at,
    )


class Registry:
    """A document and job repository pair over one connection."""

    def __init__(self, database: SqliteDatabase) -> None:
        self.connection: SqliteConnection = database.connect()
        self.documents = SqliteDocumentRepository(self.connection)
        self.jobs = SqliteIngestionJobRepository(self.connection)

    def close(self) -> None:
        self.connection.close()

    async def seed_document(self, *, versions: int = 1) -> UUID:
        record = await self.documents.create(make_record())
        for number in range(1, versions + 1):
            await self.documents.add_version(make_version(record.document_id, number))
        return record.document_id

    async def seed_job(self, key: str | None = None, **kwargs: object) -> IngestionJob:
        document_id = await self.seed_document()
        job = make_queued_job(document_id, **kwargs)  # type: ignore[arg-type]
        return await self.jobs.enqueue(
            job, idempotency_key=key or uuid4().hex, request_fingerprint=FINGERPRINT
        )


@contextmanager
def raw_db(path: Path) -> Iterator[sqlite3.Connection]:
    """A short-lived plain connection that commits on success and always closes."""
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
