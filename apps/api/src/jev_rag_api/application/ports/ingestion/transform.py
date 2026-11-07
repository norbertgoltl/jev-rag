from typing import Protocol
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import DocumentLanguage
from jev_rag_api.domain.ingestion.models import DocumentChunk, ExtractedBlock, ExtractionResult


class TextNormalizer(Protocol):
    """Meaning-preserving cleanup that keeps page, section, and source locators."""

    def normalize(self, result: ExtractionResult) -> tuple[ExtractedBlock, ...]: ...


class DocumentChunker(Protocol):
    """Produces an ordered, reproducible chunk sequence. Raises ``IngestionInvalidChunkError``."""

    def chunk(
        self,
        blocks: tuple[ExtractedBlock, ...],
        *,
        document_id: UUID,
        document_version: int,
        index_generation_id: UUID,
        language: DocumentLanguage,
    ) -> tuple[DocumentChunk, ...]: ...
