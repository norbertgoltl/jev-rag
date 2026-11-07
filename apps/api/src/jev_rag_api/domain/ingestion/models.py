import math
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    UUID4,
    UUID5,
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from .enums import (
    BlockKind,
    DistanceMetric,
    DocumentLanguage,
    IndexGenerationState,
    JobStage,
    JobStatus,
    JobType,
    Visibility,
)
from .errors import ERROR_CODES
from .identifiers import derive_chunk_id, text_sha256

PAYLOAD_SCHEMA_VERSION: Literal[1] = 1


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("Value must contain a non-whitespace character")
    return value


def _require_finite(value: tuple[float, ...]) -> tuple[float, ...]:
    if not all(math.isfinite(item) for item in value):
        raise ValueError("Vector elements must be finite")
    return value


# Naive datetimes are rejected. Aware values are converted to UTC explicitly.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
Text = Annotated[str, StringConstraints(min_length=1), AfterValidator(_require_non_blank)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[int, Field(ge=1)]
Page = Annotated[int, Field(ge=1)]
Vector = Annotated[tuple[float, ...], Field(min_length=1), AfterValidator(_require_finite)]
SectionPath = tuple[Text, ...]
SourceName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255, pattern=r"^[^/\\\x00-\x1f\x7f]+$"),
    AfterValidator(_require_non_blank),
]
MediaType = Annotated[
    str,
    StringConstraints(
        max_length=255,
        pattern=r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$",
    ),
]
StorageKey = Annotated[
    str,
    StringConstraints(max_length=512, pattern=r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$"),
]


def _reject_dot_segments(value: str) -> str:
    if any(segment in {".", ".."} for segment in value.split("/")):
        raise ValueError("Storage key must not contain dot segments")
    return value


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _check_page_range(page_start: int | None, page_end: int | None) -> None:
    if (page_start is None) != (page_end is None):
        raise ValueError("page_start and page_end must both be set or both be None")
    if page_start is not None and page_end is not None and page_end < page_start:
        raise ValueError("page_end must not be lower than page_start")


class DocumentRecord(Model):
    document_id: UUID4
    created_at: UtcDatetime
    active_version: Version | None = None
    active_index_generation_id: UUID4 | None = None
    deleted_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_active_pointer(self) -> Self:
        if (self.active_version is None) != (self.active_index_generation_id is None):
            raise ValueError("Active version and active generation must be set together")
        if self.deleted_at is not None and self.active_version is not None:
            raise ValueError("A deleted document must not have an active generation")
        return self


class DocumentVersion(Model):
    document_id: UUID4
    version: Version
    content_sha256: Sha256
    source_name: SourceName
    media_type: MediaType
    storage_key: Annotated[StorageKey, AfterValidator(_reject_dot_segments)]
    created_at: UtcDatetime


class IndexGeneration(Model):
    generation_id: UUID4
    document_id: UUID4
    document_version: Version
    pipeline_fingerprint: Sha256
    state: IndexGenerationState
    created_at: UtcDatetime


class IngestionJob(Model):
    job_id: UUID4
    job_type: JobType
    document_id: UUID4
    document_version: Version | None = None
    index_generation_id: UUID4 | None = None
    status: JobStatus
    stage: JobStage | None = None
    attempt: int = Field(ge=0)
    created_at: UtcDatetime
    updated_at: UtcDatetime
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.job_type in {JobType.INGEST, JobType.REINDEX} and self.document_version is None:
            raise ValueError("Ingest and reindex jobs require a document version")
        if self.status is JobStatus.PROCESSING and self.stage is None:
            raise ValueError("A processing job requires a stage")
        if self.status in {JobStatus.QUEUED, JobStatus.COMPLETED} and self.stage is not None:
            raise ValueError("Queued and completed jobs carry no stage")
        if self.status is not JobStatus.QUEUED and self.attempt < 1:
            raise ValueError("A started job requires attempt >= 1")
        if (self.status is JobStatus.FAILED) != (self.error_code is not None):
            raise ValueError("error_code must be set exactly when the job failed")
        if self.error_code is not None and self.error_code not in ERROR_CODES:
            raise ValueError("Unknown ingestion error code")
        return self


class SourceSpan(Model):
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    locator: Text | None = None

    @model_validator(mode="after")
    def validate_span(self) -> Self:
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("Offsets must both be set or both be None")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must not precede start_offset")
        if self.start_offset is None and self.locator is None:
            raise ValueError("A source span needs offsets or a locator")
        return self


class ExtractedBlock(Model):
    block_index: int = Field(ge=0)
    text: Text
    kind: BlockKind
    page: Page | None = None
    section_path: SectionPath = ()
    source_span: SourceSpan | None = None


class ExtractionResult(Model):
    document_id: UUID4
    document_version: Version
    parser_id: Text
    parser_version: Text
    blocks: tuple[ExtractedBlock, ...] = ()
    warnings: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def validate_block_order(self) -> Self:
        if [block.block_index for block in self.blocks] != list(range(len(self.blocks))):
            raise ValueError("Block indexes must be consecutive from 0 in order")
        return self


class DocumentChunk(Model):
    chunk_id: UUID5
    document_id: UUID4
    document_version: Version
    index_generation_id: UUID4
    chunk_index: int = Field(ge=0)
    text: Text
    token_count: int = Field(gt=0)
    language: DocumentLanguage
    page_start: Page | None = None
    page_end: Page | None = None
    section_path: SectionPath = ()
    content_sha256: Sha256
    chunker_version: Text

    @model_validator(mode="after")
    def validate_chunk(self) -> Self:
        _check_page_range(self.page_start, self.page_end)
        if self.content_sha256 != text_sha256(self.text):
            raise ValueError("content_sha256 does not match the chunk text")
        expected_id = derive_chunk_id(
            document_id=self.document_id,
            document_version=self.document_version,
            index_generation_id=self.index_generation_id,
            chunk_index=self.chunk_index,
            content_sha256=self.content_sha256,
        )
        if self.chunk_id != expected_id:
            raise ValueError("chunk_id does not match the deterministic identifier")
        return self


class EmbeddingModelInfo(Model):
    model_id: Text
    dimension: int = Field(gt=0)
    distance_metric: DistanceMetric


class EmbeddingResult(Model):
    chunk_id: UUID5
    model_id: Text
    vector: Vector
    dimension: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dimension(self) -> Self:
        if self.dimension != len(self.vector):
            raise ValueError("dimension does not match the vector length")
        return self


class VectorPointPayload(Model):
    schema_version: Literal[1]
    document_id: UUID4
    document_version: Version
    index_generation_id: UUID4
    chunk_id: UUID5
    chunk_index: int = Field(ge=0)
    text: Text
    language: DocumentLanguage
    source_name: SourceName
    page_start: Page | None = None
    page_end: Page | None = None
    section_path: SectionPath = ()
    embedding_model_id: Text
    visibility: Visibility

    @model_validator(mode="after")
    def validate_pages(self) -> Self:
        _check_page_range(self.page_start, self.page_end)
        return self

    @classmethod
    def from_chunk(
        cls,
        chunk: DocumentChunk,
        *,
        source_name: str,
        embedding_model_id: str,
        visibility: Visibility,
    ) -> Self:
        return cls(
            schema_version=PAYLOAD_SCHEMA_VERSION,
            document_id=chunk.document_id,
            document_version=chunk.document_version,
            index_generation_id=chunk.index_generation_id,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            language=chunk.language,
            source_name=source_name,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_path=chunk.section_path,
            embedding_model_id=embedding_model_id,
            visibility=visibility,
        )


class VectorPoint(Model):
    point_id: UUID5
    vector: Vector
    payload: VectorPointPayload

    @model_validator(mode="after")
    def validate_point_id(self) -> Self:
        if self.point_id != self.payload.chunk_id:
            raise ValueError("point_id must equal payload.chunk_id")
        return self


class WriteReceipt(Model):
    index_generation_id: UUID4
    point_count: int = Field(ge=0)


class IndexVerification(Model):
    index_generation_id: UUID4
    expected_count: int = Field(ge=0)
    found_count: int = Field(ge=0)

    @property
    def is_complete(self) -> bool:
        return self.expected_count == self.found_count
