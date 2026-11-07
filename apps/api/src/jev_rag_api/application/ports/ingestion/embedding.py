from collections.abc import Sequence
from typing import Protocol

from jev_rag_api.domain.ingestion.models import DocumentChunk, EmbeddingModelInfo, EmbeddingResult


class EmbeddingProvider(Protocol):
    """Embedding provider with separate document and query modes.

    Model-specific query and document prefixes belong to the implementation. Transient
    failures raise ``IngestionEmbeddingUnavailableError``.
    """

    def describe_model(self) -> EmbeddingModelInfo: ...

    async def embed_documents(
        self, chunks: Sequence[DocumentChunk]
    ) -> tuple[EmbeddingResult, ...]: ...

    async def embed_query(self, text: str) -> tuple[float, ...]: ...
