import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from builders import NOW, SHA, make_chunk, make_job, make_payload
from pydantic import ValidationError

from jev_rag_api.domain.ingestion.enums import (
    BlockKind,
    DistanceMetric,
    DocumentLanguage,
    IndexGenerationState,
    JobStage,
    JobStatus,
    JobType,
    Visibility,
)
from jev_rag_api.domain.ingestion.errors import (
    ERROR_CODES,
    IngestionError,
    IngestionInvalidStateError,
)
from jev_rag_api.domain.ingestion.identifiers import (
    INGESTION_NAMESPACE,
    derive_chunk_id,
    sha256_hex,
)
from jev_rag_api.domain.ingestion.models import (
    DocumentChunk,
    DocumentRecord,
    DocumentVersion,
    EmbeddingModelInfo,
    EmbeddingResult,
    ExtractedBlock,
    ExtractionResult,
    IndexGeneration,
    IndexVerification,
    SourceSpan,
    VectorPoint,
    VectorPointPayload,
)
from jev_rag_api.domain.ingestion.transitions import (
    transition_job,
    validate_generation_transition,
    validate_job_transition,
)


def version(**overrides: Any) -> DocumentVersion:
    values: dict[str, Any] = {
        "document_id": uuid4(),
        "version": 1,
        "content_sha256": SHA,
        "source_name": "guide.pdf",
        "media_type": "application/pdf",
        "storage_key": "ab/cd/abcdef",
        "created_at": NOW,
    }
    values.update(overrides)
    return DocumentVersion.model_validate(values)


class TestIdentity:
    def test_same_hash_different_documents_are_distinct(self) -> None:
        first = version()
        second = version()
        assert first.content_sha256 == second.content_sha256
        assert first.document_id != second.document_id

    def test_chunk_id_is_deterministic_and_generation_scoped(self) -> None:
        document_id, generation_id = uuid4(), uuid4()
        args = dict(document_id=document_id, document_version=1, chunk_index=0, content_sha256=SHA)
        first = derive_chunk_id(index_generation_id=generation_id, **args)  # type: ignore[arg-type]
        again = derive_chunk_id(index_generation_id=generation_id, **args)  # type: ignore[arg-type]
        other = derive_chunk_id(index_generation_id=uuid4(), **args)  # type: ignore[arg-type]
        assert first == again != other
        assert first.version == 5

    def test_chunk_id_known_vector(self) -> None:
        # Guards the namespace and canonical tuple layout against accidental change.
        actual = derive_chunk_id(
            document_id=UUID("11111111-1111-4111-8111-111111111111"),
            document_version=3,
            index_generation_id=UUID("22222222-2222-4222-8222-222222222222"),
            chunk_index=7,
            content_sha256=SHA,
        )
        assert str(INGESTION_NAMESPACE) == "821ab20b-0823-42ac-b401-92927700a19e"
        assert actual == UUID("734f3c3b-9457-5b05-8b03-aa58a5be1bc9")

    def test_sha256_hex_is_lowercase_64(self) -> None:
        assert len(sha256_hex(b"x")) == 64


class TestDocumentModels:
    def test_unchanged_source_reindex_keeps_version_new_generation(self) -> None:
        doc_version = version()
        first = IndexGeneration(
            generation_id=uuid4(),
            document_id=doc_version.document_id,
            document_version=doc_version.version,
            pipeline_fingerprint="b" * 64,
            state=IndexGenerationState.STAGED,
            created_at=NOW,
        )
        second = first.model_copy(
            update={"generation_id": uuid4(), "pipeline_fingerprint": "c" * 64}
        )
        assert first.document_version == second.document_version
        assert first.generation_id != second.generation_id

    @pytest.mark.parametrize(
        "overrides",
        [
            {"version": 0},
            {"content_sha256": "a" * 63},
            {"content_sha256": "g" * 64},
            {"content_sha256": "A" * 64},
            {"storage_key": "/etc/passwd"},
            {"storage_key": "../escape"},
            {"storage_key": "a/./b"},
            {"storage_key": "a\\b"},
            {"source_name": "dir/file.txt"},
            {"source_name": "  "},
            {"media_type": "pdf"},
            {"created_at": datetime(2026, 1, 1)},
        ],
    )
    def test_invalid_version(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            version(**overrides)

    def test_timestamps_are_normalized_to_utc(self) -> None:
        local = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
        assert version(created_at=local).created_at == NOW.replace(hour=12)
        assert version(created_at=local).created_at.utcoffset() == timedelta(0)

    def test_record_requires_paired_active_pointer(self) -> None:
        with pytest.raises(ValidationError):
            DocumentRecord(document_id=uuid4(), created_at=NOW, active_version=1)

    def test_deleted_record_cannot_be_active(self) -> None:
        with pytest.raises(ValidationError):
            DocumentRecord(
                document_id=uuid4(),
                created_at=NOW,
                active_version=1,
                active_index_generation_id=uuid4(),
                deleted_at=NOW,
            )

    def test_models_are_frozen_and_forbid_extra(self) -> None:
        record = DocumentRecord(document_id=uuid4(), created_at=NOW)
        with pytest.raises(ValidationError):
            record.active_version = 1
        with pytest.raises(ValidationError):
            DocumentRecord.model_validate({"document_id": uuid4(), "created_at": NOW, "x": 1})

    def test_non_v4_document_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DocumentRecord(document_id=UUID(int=1, version=1), created_at=NOW)


class TestJobs:
    def test_valid_lifecycle(self) -> None:
        job = make_job()
        claimed = transition_job(job, JobStatus.PROCESSING, now=NOW)
        assert (claimed.attempt, claimed.stage) == (1, JobStage.VALIDATING)
        done = transition_job(claimed, JobStatus.COMPLETED, now=NOW)
        assert done.stage is None

    def test_failure_keeps_stage_and_retry_opens_new_attempt(self) -> None:
        claimed = transition_job(
            make_job(), JobStatus.PROCESSING, now=NOW, stage=JobStage.EMBEDDING
        )
        failed = transition_job(
            claimed, JobStatus.FAILED, now=NOW, error_code="ING_EMBEDDING_UNAVAILABLE"
        )
        assert failed.stage is JobStage.EMBEDDING
        queued = transition_job(failed, JobStatus.QUEUED, now=NOW)
        assert (queued.error_code, queued.stage, queued.attempt) == (None, None, 1)
        assert transition_job(queued, JobStatus.PROCESSING, now=NOW).attempt == 2

    def test_recovery_returns_processing_to_queued(self) -> None:
        claimed = transition_job(make_job(), JobStatus.PROCESSING, now=NOW)
        assert transition_job(claimed, JobStatus.QUEUED, now=NOW).status is JobStatus.QUEUED

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (JobStatus.COMPLETED, JobStatus.PROCESSING),
            (JobStatus.COMPLETED, JobStatus.QUEUED),
            (JobStatus.COMPLETED, JobStatus.FAILED),
            (JobStatus.QUEUED, JobStatus.COMPLETED),
            (JobStatus.QUEUED, JobStatus.FAILED),
            (JobStatus.FAILED, JobStatus.PROCESSING),
            (JobStatus.FAILED, JobStatus.COMPLETED),
            (JobStatus.PROCESSING, JobStatus.PROCESSING),
        ],
    )
    def test_forbidden_transitions(self, current: JobStatus, target: JobStatus) -> None:
        with pytest.raises(IngestionInvalidStateError):
            validate_job_transition(current, target)

    def test_failure_requires_known_error_code(self) -> None:
        claimed = transition_job(make_job(), JobStatus.PROCESSING, now=NOW)
        with pytest.raises(ValidationError):
            transition_job(claimed, JobStatus.FAILED, now=NOW)
        with pytest.raises(ValidationError):
            transition_job(claimed, JobStatus.FAILED, now=NOW, error_code="boom")

    @pytest.mark.parametrize(
        "overrides",
        [
            {"attempt": -1},
            {"status": JobStatus.PROCESSING, "attempt": 1},
            {"status": JobStatus.QUEUED, "stage": JobStage.CHUNKING},
            {"status": JobStatus.PROCESSING, "attempt": 0, "stage": JobStage.CHUNKING},
            {"error_code": "ING_CONFLICT"},
            {"document_version": None},
            {"updated_at": NOW - timedelta(seconds=1)},
        ],
    )
    def test_invalid_job(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            make_job(**overrides)

    def test_delete_job_needs_no_version(self) -> None:
        assert make_job(job_type=JobType.DELETE, document_version=None).document_version is None

    def test_generation_transitions(self) -> None:
        validate_generation_transition(IndexGenerationState.STAGED, IndexGenerationState.ACTIVE)
        validate_generation_transition(IndexGenerationState.ACTIVE, IndexGenerationState.SUPERSEDED)
        for current, target in [
            (IndexGenerationState.SUPERSEDED, IndexGenerationState.ACTIVE),
            (IndexGenerationState.FAILED, IndexGenerationState.STAGED),
            (IndexGenerationState.STAGED, IndexGenerationState.SUPERSEDED),
        ]:
            with pytest.raises(IngestionInvalidStateError):
                validate_generation_transition(current, target)


class TestExtractionAndChunks:
    def block(self, index: int = 0, **overrides: Any) -> ExtractedBlock:
        values: dict[str, Any] = {"block_index": index, "text": "Body", "kind": BlockKind.PARAGRAPH}
        values.update(overrides)
        return ExtractedBlock.model_validate(values)

    def test_missing_page_stays_none(self) -> None:
        assert self.block().page is None

    @pytest.mark.parametrize("overrides", [{"page": 0}, {"text": "   "}, {"block_index": -1}])
    def test_invalid_block(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            self.block(**overrides)

    def test_block_order_must_be_consecutive(self) -> None:
        kwargs: dict[str, Any] = {
            "document_id": uuid4(),
            "document_version": 1,
            "parser_id": "p",
            "parser_version": "1",
        }
        ExtractionResult(blocks=(self.block(0), self.block(1)), **kwargs)
        ExtractionResult(**kwargs)
        with pytest.raises(ValidationError):
            ExtractionResult(blocks=(self.block(1), self.block(0)), **kwargs)

    def test_source_span_rules(self) -> None:
        SourceSpan(start_offset=0, end_offset=5)
        SourceSpan(locator="p1")
        for values in [{}, {"start_offset": 5, "end_offset": 1}, {"start_offset": 1}]:
            with pytest.raises(ValidationError):
                SourceSpan.model_validate(values)

    def test_valid_chunk(self) -> None:
        chunk = make_chunk()
        assert chunk.chunk_id.version == 5

    @pytest.mark.parametrize(
        "overrides",
        [
            {"text": ""},
            {"text": "  "},
            {"chunk_index": -1},
            {"token_count": 0},
            {"page_start": 3, "page_end": 2},
            {"page_start": 1, "page_end": None},
            {"page_start": 0, "page_end": 1},
            {"content_sha256": "0" * 64},
            {"content_sha256": "xyz"},
        ],
    )
    def test_invalid_chunk(self, overrides: dict[str, Any]) -> None:
        values = make_chunk().model_dump()
        values.update(overrides)
        with pytest.raises(ValidationError):
            DocumentChunk.model_validate(values)

    def test_tampered_chunk_id_rejected(self) -> None:
        values = make_chunk().model_dump()
        values["chunk_id"] = derive_chunk_id(
            document_id=uuid4(),
            document_version=1,
            index_generation_id=uuid4(),
            chunk_index=0,
            content_sha256=SHA,
        )
        with pytest.raises(ValidationError):
            DocumentChunk.model_validate(values)


class TestEmbeddingAndPayload:
    def test_valid_embedding(self) -> None:
        chunk = make_chunk()
        result = EmbeddingResult(
            chunk_id=chunk.chunk_id, model_id="m", vector=(0.1, 0.2), dimension=2
        )
        assert result.dimension == 2

    @pytest.mark.parametrize(
        "vector",
        [(float("nan"), 1.0), (float("inf"), 1.0), (float("-inf"), 1.0), ()],
    )
    def test_invalid_vector(self, vector: tuple[float, ...]) -> None:
        with pytest.raises(ValidationError):
            EmbeddingResult(
                chunk_id=make_chunk().chunk_id, model_id="m", vector=vector, dimension=2
            )

    def test_dimension_mismatch(self) -> None:
        with pytest.raises(ValidationError):
            EmbeddingResult(
                chunk_id=make_chunk().chunk_id, model_id="m", vector=(1.0,), dimension=2
            )

    def test_model_info_requires_positive_dimension(self) -> None:
        with pytest.raises(ValidationError):
            EmbeddingModelInfo(model_id="m", dimension=0, distance_metric=DistanceMetric.COSINE)

    def test_payload_json_round_trip_and_schema_version(self) -> None:
        payload = make_payload()
        dumped = json.loads(payload.model_dump_json())
        assert dumped["schema_version"] == 1
        assert VectorPointPayload.model_validate_json(json.dumps(dumped)) == payload
        assert set(payload.model_dump(mode="json")) == {
            "schema_version", "document_id", "document_version", "index_generation_id",
            "chunk_id", "chunk_index", "text", "language", "source_name", "page_start",
            "page_end", "section_path", "embedding_model_id", "visibility",
        }  # fmt: skip

    def test_payload_requires_schema_version(self) -> None:
        values = make_payload().model_dump()
        del values["schema_version"]
        with pytest.raises(ValidationError):
            VectorPointPayload.model_validate(values)
        values["schema_version"] = 2
        with pytest.raises(ValidationError):
            VectorPointPayload.model_validate(values)

    def test_payload_page_rule(self) -> None:
        values = make_payload().model_dump()
        values.update(page_start=4, page_end=3)
        with pytest.raises(ValidationError):
            VectorPointPayload.model_validate(values)

    def test_point_id_must_match_payload(self) -> None:
        payload = make_payload()
        VectorPoint(point_id=payload.chunk_id, vector=(1.0,), payload=payload)
        with pytest.raises(ValidationError):
            VectorPoint(point_id=make_chunk().chunk_id, vector=(1.0,), payload=payload)

    def test_verification_completeness(self) -> None:
        assert IndexVerification(
            index_generation_id=uuid4(), expected_count=2, found_count=2
        ).is_complete
        assert not IndexVerification(
            index_generation_id=uuid4(), expected_count=2, found_count=1
        ).is_complete

    def test_enum_values_are_stable(self) -> None:
        assert {item.value for item in DocumentLanguage} == {"hu", "en", "mixed", "unknown"}
        assert {item.value for item in Visibility} == {"staged", "active", "inactive"}


class TestErrors:
    def test_error_codes_and_retry_defaults(self) -> None:
        from jev_rag_api.domain.ingestion import errors

        retryable = {
            cls.code
            for cls in vars(errors).values()
            if isinstance(cls, type) and issubclass(cls, IngestionError) and cls.retryable
        }
        assert retryable == {"ING_EMBEDDING_UNAVAILABLE", "ING_VECTOR_STORE_UNAVAILABLE"}
        assert "ING_INDEX_INCOMPATIBLE" in ERROR_CODES
        assert len(ERROR_CODES) == 12
        assert str(IngestionInvalidStateError()) == "ING_INVALID_STATE"
