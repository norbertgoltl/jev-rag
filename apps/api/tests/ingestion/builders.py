from datetime import UTC, datetime
from uuid import UUID, uuid4

from jev_rag_api.domain.ingestion.enums import (
    DocumentLanguage,
    JobStatus,
    JobType,
    Visibility,
)
from jev_rag_api.domain.ingestion.identifiers import derive_chunk_id, text_sha256
from jev_rag_api.domain.ingestion.models import (
    DocumentChunk,
    IngestionJob,
    VectorPointPayload,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
SHA = "a" * 64


def make_chunk(
    *,
    document_id: UUID | None = None,
    generation_id: UUID | None = None,
    chunk_index: int = 0,
    text: str = "Hello world",
    page_start: int | None = 1,
    page_end: int | None = 2,
) -> DocumentChunk:
    document_id = document_id or uuid4()
    generation_id = generation_id or uuid4()
    digest = text_sha256(text)
    return DocumentChunk(
        chunk_id=derive_chunk_id(
            document_id=document_id,
            document_version=1,
            index_generation_id=generation_id,
            chunk_index=chunk_index,
            content_sha256=digest,
        ),
        document_id=document_id,
        document_version=1,
        index_generation_id=generation_id,
        chunk_index=chunk_index,
        text=text,
        token_count=3,
        language=DocumentLanguage.EN,
        page_start=page_start,
        page_end=page_end,
        section_path=("Intro",),
        content_sha256=digest,
        chunker_version="test-1",
    )


def make_job(**overrides: object) -> IngestionJob:
    values: dict[str, object] = {
        "job_id": uuid4(),
        "job_type": JobType.INGEST,
        "document_id": uuid4(),
        "document_version": 1,
        "status": JobStatus.QUEUED,
        "attempt": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return IngestionJob.model_validate(values)


def make_payload(chunk: DocumentChunk | None = None) -> VectorPointPayload:
    return VectorPointPayload.from_chunk(
        chunk or make_chunk(),
        source_name="guide.pdf",
        embedding_model_id="model-x",
        visibility=Visibility.STAGED,
    )
