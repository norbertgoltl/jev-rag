from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import Visibility
from jev_rag_api.domain.ingestion.models import (
    EmbeddingModelInfo,
    IndexVerification,
    VectorPoint,
    WriteReceipt,
)


class VectorIndex(Protocol):
    """Writes indexed points. It is not the authority on the document lifecycle.

    Transient failures raise ``IngestionVectorStoreUnavailableError``. A failure never
    returns a false success.
    """

    async def ensure_compatible(
        self, model: EmbeddingModelInfo, *, payload_schema_version: int
    ) -> None:
        """Raise ``IngestionIndexIncompatibleError`` on any mismatch. Never convert silently."""
        ...

    async def upsert(self, points: Sequence[VectorPoint]) -> WriteReceipt: ...

    async def set_visibility(
        self, document_id: UUID, index_generation_id: UUID, visibility: Visibility
    ) -> WriteReceipt: ...

    async def delete_generation(
        self, document_id: UUID, index_generation_id: UUID
    ) -> WriteReceipt: ...

    async def verify(
        self, document_id: UUID, index_generation_id: UUID, expected_point_ids: Sequence[UUID]
    ) -> IndexVerification: ...
