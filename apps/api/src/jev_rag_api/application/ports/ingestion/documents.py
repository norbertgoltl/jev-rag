from datetime import datetime
from typing import Protocol
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import IndexGenerationState
from jev_rag_api.domain.ingestion.models import DocumentRecord, DocumentVersion, IndexGeneration


class DocumentRepository(Protocol):
    """Durable document, version, and generation state.

    Raises ``IngestionNotFoundError``, ``IngestionConflictError``, or
    ``IngestionInvalidStateError``. The registry is the authority on the active generation.
    """

    async def create(self, document: DocumentRecord) -> DocumentRecord: ...

    async def get(self, document_id: UUID) -> DocumentRecord: ...

    async def add_version(self, version: DocumentVersion) -> DocumentVersion: ...

    async def get_version(self, document_id: UUID, version: int) -> DocumentVersion: ...

    async def add_generation(self, generation: IndexGeneration) -> IndexGeneration: ...

    async def set_generation_state(
        self, generation_id: UUID, state: IndexGenerationState
    ) -> IndexGeneration: ...

    async def get_active(self, document_id: UUID) -> IndexGeneration | None: ...

    async def publish_generation(
        self, generation_id: UUID, *, expected_active_generation_id: UUID | None
    ) -> DocumentRecord:
        """Compare-and-set the active pointer. Raises ``IngestionConflictError`` on mismatch."""
        ...

    async def mark_deleted(self, document_id: UUID, *, deleted_at: datetime) -> DocumentRecord: ...


class SourceDocumentStore(Protocol):
    """Opaque source storage. Callers never supply a path, only receive a generated key."""

    async def put(self, content: bytes) -> str: ...

    async def get(self, storage_key: str) -> bytes: ...

    async def delete(self, storage_key: str) -> None: ...
