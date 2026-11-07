from datetime import datetime
from typing import Protocol
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import JobStage
from jev_rag_api.domain.ingestion.models import IngestionJob


class IngestionJobRepository(Protocol):
    """Durable job queue. ``attempt`` is the fencing token for every update after a claim."""

    async def enqueue(
        self, job: IngestionJob, *, idempotency_key: str, request_fingerprint: str
    ) -> IngestionJob:
        """Create a queued job.

        The same key and fingerprint return the stored job. The same key with another
        fingerprint raises ``IngestionConflictError``.
        """
        ...

    async def get(self, job_id: UUID) -> IngestionJob: ...

    async def claim(
        self, *, worker_id: str, lease_seconds: int, now: datetime
    ) -> IngestionJob | None:
        """Atomically move one queued job to processing and open a new attempt."""
        ...

    async def heartbeat(
        self, job_id: UUID, *, attempt: int, lease_seconds: int, now: datetime
    ) -> None: ...

    async def record_stage(
        self, job_id: UUID, *, attempt: int, stage: JobStage, now: datetime
    ) -> None: ...

    async def complete(self, job_id: UUID, *, attempt: int, now: datetime) -> IngestionJob: ...

    async def fail(
        self, job_id: UUID, *, attempt: int, error_code: str, now: datetime
    ) -> IngestionJob: ...

    async def requeue(self, job_id: UUID, *, now: datetime) -> IngestionJob:
        """Explicit retry of a failed job. History is preserved."""
        ...

    async def release_expired(self, *, now: datetime) -> tuple[UUID, ...]:
        """Return expired processing jobs to the queue and report their IDs."""
        ...
