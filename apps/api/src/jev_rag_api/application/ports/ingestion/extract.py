from typing import Protocol
from uuid import UUID

from jev_rag_api.domain.ingestion.models import ExtractionResult


class DocumentExtractor(Protocol):
    """Synchronous, CPU-bound extraction. Must not mutate its inputs."""

    def supports(self, media_type: str) -> bool: ...

    def extract(
        self,
        *,
        document_id: UUID,
        document_version: int,
        source_name: str,
        media_type: str,
        content: bytes,
    ) -> ExtractionResult: ...
