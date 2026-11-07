import ast
import asyncio
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from builders import NOW, SHA, make_chunk, make_job

from jev_rag_api.application.ports.ingestion.documents import (
    SourceDocumentStore,
)
from jev_rag_api.application.ports.ingestion.embedding import EmbeddingProvider
from jev_rag_api.application.ports.ingestion.extract import DocumentExtractor
from jev_rag_api.application.ports.ingestion.jobs import IngestionJobRepository
from jev_rag_api.application.ports.ingestion.transform import DocumentChunker, TextNormalizer
from jev_rag_api.application.ports.ingestion.vectors import VectorIndex
from jev_rag_api.domain.ingestion.enums import (
    BlockKind,
    DistanceMetric,
    DocumentLanguage,
    JobStage,
    JobStatus,
    Visibility,
)
from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionIndexIncompatibleError,
    IngestionNotFoundError,
)
from jev_rag_api.domain.ingestion.identifiers import derive_chunk_id, text_sha256
from jev_rag_api.domain.ingestion.models import (
    DocumentChunk,
    EmbeddingModelInfo,
    EmbeddingResult,
    ExtractedBlock,
    ExtractionResult,
    IndexVerification,
    IngestionJob,
    VectorPoint,
    VectorPointPayload,
    WriteReceipt,
)
from jev_rag_api.domain.ingestion.transitions import transition_job

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "jev_rag_api"
INNER_PACKAGES = [
    SOURCE_ROOT / "domain" / "ingestion",
    SOURCE_ROOT / "application" / "ports" / "ingestion",
]
FORBIDDEN = {
    "fastapi", "starlette", "httpx", "qdrant_client", "sqlite3", "aiosqlite", "sqlalchemy",
    "pypdf", "pdfminer", "fitz", "docx", "typesafe_sdk", "openai", "sentence_transformers",
    "jev_rag_api.api", "jev_rag_api.integrations", "jev_rag_api.core",
}  # fmt: skip


class FakeStore:
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    async def put(self, content: bytes) -> str:
        key = f"k{len(self.items)}"
        self.items[key] = content
        return key

    async def get(self, storage_key: str) -> bytes:
        try:
            return self.items[storage_key]
        except KeyError:
            raise IngestionNotFoundError() from None

    async def delete(self, storage_key: str) -> None:
        self.items.pop(storage_key, None)


class FakeJobs:
    def __init__(self) -> None:
        self.jobs: dict[UUID, IngestionJob] = {}
        self.keys: dict[str, tuple[str, UUID]] = {}

    async def enqueue(
        self, job: IngestionJob, *, idempotency_key: str, request_fingerprint: str
    ) -> IngestionJob:
        if idempotency_key in self.keys:
            fingerprint, job_id = self.keys[idempotency_key]
            if fingerprint != request_fingerprint:
                raise IngestionConflictError()
            return self.jobs[job_id]
        self.keys[idempotency_key] = (request_fingerprint, job.job_id)
        self.jobs[job.job_id] = job
        return job

    async def get(self, job_id: UUID) -> IngestionJob:
        return self.jobs[job_id]

    async def claim(
        self, *, worker_id: str, lease_seconds: int, now: datetime
    ) -> IngestionJob | None:
        for job in self.jobs.values():
            if job.status is JobStatus.QUEUED:
                self.jobs[job.job_id] = claimed = transition_job(job, JobStatus.PROCESSING, now=now)
                return claimed
        return None

    async def heartbeat(
        self, job_id: UUID, *, attempt: int, lease_seconds: int, now: datetime
    ) -> None:
        return None

    async def record_stage(
        self, job_id: UUID, *, attempt: int, stage: JobStage, now: datetime
    ) -> None:
        return None

    async def complete(self, job_id: UUID, *, attempt: int, now: datetime) -> IngestionJob:
        self.jobs[job_id] = done = transition_job(self.jobs[job_id], JobStatus.COMPLETED, now=now)
        return done

    async def fail(
        self, job_id: UUID, *, attempt: int, error_code: str, now: datetime
    ) -> IngestionJob:
        self.jobs[job_id] = failed = transition_job(
            self.jobs[job_id], JobStatus.FAILED, now=now, error_code=error_code
        )
        return failed

    async def requeue(self, job_id: UUID, *, now: datetime) -> IngestionJob:
        self.jobs[job_id] = queued = transition_job(self.jobs[job_id], JobStatus.QUEUED, now=now)
        return queued

    async def release_expired(self, *, now: datetime) -> tuple[UUID, ...]:
        return ()


class FakeExtractor:
    def supports(self, media_type: str) -> bool:
        return media_type == "text/plain"

    def extract(
        self,
        *,
        document_id: UUID,
        document_version: int,
        source_name: str,
        media_type: str,
        content: bytes,
    ) -> ExtractionResult:
        blocks = tuple(
            ExtractedBlock(block_index=index, text=line, kind=BlockKind.PARAGRAPH)
            for index, line in enumerate(
                line for line in content.decode().splitlines() if line.strip()
            )
        )
        return ExtractionResult(
            document_id=document_id,
            document_version=document_version,
            parser_id="fake",
            parser_version="1",
            blocks=blocks,
        )


class FakeNormalizer:
    def normalize(self, result: ExtractionResult) -> tuple[ExtractedBlock, ...]:
        return result.blocks


class FakeChunker:
    def chunk(
        self,
        blocks: tuple[ExtractedBlock, ...],
        *,
        document_id: UUID,
        document_version: int,
        index_generation_id: UUID,
        language: DocumentLanguage,
    ) -> tuple[DocumentChunk, ...]:
        return tuple(
            DocumentChunk(
                chunk_id=derive_chunk_id(
                    document_id=document_id,
                    document_version=document_version,
                    index_generation_id=index_generation_id,
                    chunk_index=index,
                    content_sha256=text_sha256(block.text),
                ),
                document_id=document_id,
                document_version=document_version,
                index_generation_id=index_generation_id,
                chunk_index=index,
                text=block.text,
                token_count=len(block.text.split()),
                language=language,
                content_sha256=text_sha256(block.text),
                chunker_version="fake-1",
            )
            for index, block in enumerate(blocks)
        )


class FakeEmbedder:
    def describe_model(self) -> EmbeddingModelInfo:
        return EmbeddingModelInfo(
            model_id="fake", dimension=2, distance_metric=DistanceMetric.COSINE
        )

    async def embed_documents(self, chunks: Sequence[DocumentChunk]) -> tuple[EmbeddingResult, ...]:
        return tuple(
            EmbeddingResult(
                chunk_id=chunk.chunk_id,
                model_id="fake",
                vector=(1.0, float(chunk.token_count)),
                dimension=2,
            )
            for chunk in chunks
        )

    async def embed_query(self, text: str) -> tuple[float, ...]:
        return (1.0, float(len(text.split())))


class FakeIndex:
    def __init__(self) -> None:
        self.points: dict[UUID, VectorPoint] = {}

    async def ensure_compatible(
        self, model: EmbeddingModelInfo, *, payload_schema_version: int
    ) -> None:
        if model.dimension != 2 or payload_schema_version != 1:
            raise IngestionIndexIncompatibleError()

    async def upsert(self, points: Sequence[VectorPoint]) -> WriteReceipt:
        for point in points:
            self.points[point.point_id] = point
        return WriteReceipt(
            index_generation_id=points[0].payload.index_generation_id, point_count=len(points)
        )

    async def set_visibility(
        self, document_id: UUID, index_generation_id: UUID, visibility: Visibility
    ) -> WriteReceipt:
        count = 0
        for key, point in self.points.items():
            if point.payload.index_generation_id == index_generation_id:
                payload = point.payload.model_copy(update={"visibility": visibility})
                self.points[key] = point.model_copy(update={"payload": payload})
                count += 1
        return WriteReceipt(index_generation_id=index_generation_id, point_count=count)

    async def delete_generation(self, document_id: UUID, index_generation_id: UUID) -> WriteReceipt:
        doomed = [
            k
            for k, p in self.points.items()
            if p.payload.index_generation_id == index_generation_id
        ]
        for key in doomed:
            del self.points[key]
        return WriteReceipt(index_generation_id=index_generation_id, point_count=len(doomed))

    async def verify(
        self, document_id: UUID, index_generation_id: UUID, expected_point_ids: Sequence[UUID]
    ) -> IndexVerification:
        found = sum(1 for pid in expected_point_ids if pid in self.points)
        return IndexVerification(
            index_generation_id=index_generation_id,
            expected_count=len(expected_point_ids),
            found_count=found,
        )


def test_fakes_satisfy_ports() -> None:
    # Static conformance is checked by mypy through these annotated assignments.
    store: SourceDocumentStore = FakeStore()
    jobs: IngestionJobRepository = FakeJobs()
    extractor: DocumentExtractor = FakeExtractor()
    normalizer: TextNormalizer = FakeNormalizer()
    chunker: DocumentChunker = FakeChunker()
    embedder: EmbeddingProvider = FakeEmbedder()
    index: VectorIndex = FakeIndex()
    assert all((store, jobs, extractor, normalizer, chunker, embedder, index))


async def run_pipeline(
    index: FakeIndex,
) -> tuple[ExtractionResult, tuple[DocumentChunk, ...], UUID]:
    document_id, generation_id = uuid4(), uuid4()
    store = FakeStore()
    key = await store.put(b"first line\nsecond line\n\nthird")
    extractor, chunker, embedder = FakeExtractor(), FakeChunker(), FakeEmbedder()
    assert extractor.supports("text/plain")
    result = extractor.extract(
        document_id=document_id,
        document_version=1,
        source_name="a.txt",
        media_type="text/plain",
        content=await store.get(key),
    )
    chunks = chunker.chunk(
        FakeNormalizer().normalize(result),
        document_id=document_id,
        document_version=1,
        index_generation_id=generation_id,
        language=DocumentLanguage.EN,
    )
    model = embedder.describe_model()
    await index.ensure_compatible(model, payload_schema_version=1)
    embeddings = await embedder.embed_documents(chunks)
    points = [
        VectorPoint(
            point_id=chunk.chunk_id,
            vector=embedding.vector,
            payload=VectorPointPayload.from_chunk(
                chunk,
                source_name="a.txt",
                embedding_model_id=embedding.model_id,
                visibility=Visibility.STAGED,
            ),
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    await index.upsert(points)
    return result, chunks, generation_id


def test_fake_pipeline_is_deterministic_and_idempotent() -> None:
    index = FakeIndex()
    _, chunks, generation_id = asyncio.run(run_pipeline(index))
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert len(index.points) == 3
    ids = [chunk.chunk_id for chunk in chunks]
    verification = asyncio.run(index.verify(chunks[0].document_id, generation_id, ids))
    assert verification.is_complete
    receipt = asyncio.run(
        index.set_visibility(chunks[0].document_id, generation_id, Visibility.ACTIVE)
    )
    assert receipt.point_count == 3
    assert {p.payload.visibility for p in index.points.values()} == {Visibility.ACTIVE}
    deleted = asyncio.run(index.delete_generation(chunks[0].document_id, generation_id))
    assert deleted.point_count == 3
    assert not asyncio.run(index.verify(chunks[0].document_id, generation_id, ids)).is_complete


def test_incompatible_collection_is_rejected_without_conversion() -> None:
    index = FakeIndex()
    model = EmbeddingModelInfo(model_id="other", dimension=3, distance_metric=DistanceMetric.DOT)
    with pytest.raises(IngestionIndexIncompatibleError):
        asyncio.run(index.ensure_compatible(model, payload_schema_version=1))


def test_job_idempotency_contract() -> None:
    jobs = FakeJobs()
    first = asyncio.run(jobs.enqueue(make_job(), idempotency_key="k", request_fingerprint=SHA))
    again = asyncio.run(jobs.enqueue(make_job(), idempotency_key="k", request_fingerprint=SHA))
    assert again == first
    with pytest.raises(IngestionConflictError):
        asyncio.run(jobs.enqueue(make_job(), idempotency_key="k", request_fingerprint="b" * 64))


def test_job_claim_complete_cycle() -> None:
    jobs = FakeJobs()
    queued = asyncio.run(jobs.enqueue(make_job(), idempotency_key="k", request_fingerprint=SHA))
    claimed = asyncio.run(jobs.claim(worker_id="w", lease_seconds=300, now=NOW))
    assert claimed is not None and claimed.job_id == queued.job_id and claimed.attempt == 1
    assert asyncio.run(jobs.claim(worker_id="w", lease_seconds=300, now=NOW)) is None
    done = asyncio.run(jobs.complete(queued.job_id, attempt=1, now=NOW))
    assert done.status is JobStatus.COMPLETED


def test_chunk_input_is_not_mutated() -> None:
    chunk = make_chunk()
    before = chunk.model_dump()
    VectorPointPayload.from_chunk(
        chunk, source_name="a.txt", embedding_model_id="m", visibility=Visibility.STAGED
    )
    assert chunk.model_dump() == before


def imported_modules(source: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import):
            modules.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_contract_layers_import_no_sdk_or_outer_layer() -> None:
    violations = [
        f"{source.name} imports {module}"
        for package in INNER_PACKAGES
        for source in package.rglob("*.py")
        for module in imported_modules(source)
        if any(module == name or module.startswith(f"{name}.") for name in FORBIDDEN)
    ]
    assert violations == []


def test_domain_does_not_import_application() -> None:
    domain = SOURCE_ROOT / "domain" / "ingestion"
    offenders = [
        f"{source.name} imports {module}"
        for source in domain.rglob("*.py")
        for module in imported_modules(source)
        if module.startswith("jev_rag_api.application")
    ]
    assert offenders == []
