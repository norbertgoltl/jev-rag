# Ingestion contracts

Status: implemented by PR-ING-002. The signatures below match the code. Architecture context: [architecture](architecture.md).

## 0. Code locations

| Path (under `apps/api/src/jev_rag_api`) | Content |
| --- | --- |
| `domain/ingestion/enums.py` | Enumerations |
| `domain/ingestion/identifiers.py` | Namespace constant, SHA-256 helpers, `derive_chunk_id` |
| `domain/ingestion/models.py` | Models and invariants |
| `domain/ingestion/transitions.py` | Job and generation transition validation, `transition_job` |
| `domain/ingestion/errors.py` | `IngestionError` subclasses and `ERROR_CODES` |
| `application/ports/ingestion/` | `documents.py`, `jobs.py`, `extract.py`, `transform.py`, `embedding.py`, `vectors.py` |

`identifiers.py` and `transitions.py` are additions to the planned file list. They keep hashing and state rules out of the model module. Adapters for ING-004–006 live in `integrations/ingestion/` and are described in [intake and persistence](intake-and-persistence.md). Tests live in `apps/api/tests/ingestion/` as `test_ingestion_models.py`, `test_ingestion_contracts.py`, and `test_ingestion_settings.py`. The `test_ingestion_` prefix is required because the test tree has no packages, so pytest needs unique module names and `tests/unit/decisions/test_models.py` already exists.

## 1. Glossary

| Term | Definition |
| --- | --- |
| Document | Durable logical identity, `document_id`. |
| Document version | Source bytes of a document, numbered from 1 within the document. |
| Index generation | Index representation of one document version under one pipeline snapshot. |
| Pipeline fingerprint | SHA-256 of the canonical, sorted, versioned description of parser, normalizer, chunker, tokenizer, embedding model, and relevant settings. |
| Job | One unit of work (`ingest`, `reindex`, `delete`) with attempts. |
| Attempt | One claim of a job by a worker. Also the fencing token. |
| Chunk | A contiguous text unit with provenance, the unit of retrieval. |
| Point | A Qdrant record: stable ID, vector, payload. |

## 2. Identifiers and formats

| Identifier | Format | Rule |
| --- | --- | --- |
| `document_id` | UUIDv4 | Created with the document. |
| `job_id` | UUIDv4 | New for every work run. |
| `document_version` | int ≥ 1 | Increases within a document. |
| `index_generation_id` | UUIDv4 | New for every index generation. |
| `chunk_id` and Qdrant point ID | UUIDv5 | Deterministic, see below. |
| `content_sha256` | 64 lowercase hex characters | SHA-256 of the raw source bytes for a version, of the UTF-8 chunk text for a chunk. |
| `pipeline_fingerprint` | 64 lowercase hex characters | See glossary. Contains no secrets, absolute host paths, or timestamps. |
| `storage_key` | opaque relative key | Generated. Segments are `[A-Za-z0-9._-]+`, never `.` or `..`, never absolute. |
| Timestamps | timezone-aware UTC | Naive values are rejected. Aware non-UTC values are converted to UTC explicitly. |

Hashes are lowercase hex only. Upper-case hex is rejected so that equal digests have one spelling.

### Deterministic chunk and point ID

`chunk_id = uuid5(INGESTION_NAMESPACE, canonical_tuple)` where

```text
INGESTION_NAMESPACE = 821ab20b-0823-42ac-b401-92927700a19e
canonical_tuple     = "{document_id}:{document_version}:{index_generation_id}:{chunk_index}:{content_sha256}"
```

`document_id` and `index_generation_id` use the canonical lowercase hyphenated UUID form. `document_version` and `chunk_index` are decimal integers without padding. The generation is part of the tuple, so a staged generation never collides with the active one. A repeated write of the same generation reuses the same IDs. The namespace constant must not change. A change is a breaking identifier migration.

## 3. Enumerations

| Enum | Values |
| --- | --- |
| `DocumentLanguage` | `hu`, `en`, `mixed`, `unknown` |
| `JobStatus` | `queued`, `processing`, `completed`, `failed` |
| `JobStage` | `validating`, `extracting`, `normalizing`, `chunking`, `embedding`, `indexing`, `finalizing` |
| `JobType` | `ingest`, `reindex`, `delete` |
| `IndexGenerationState` | `staged`, `active`, `superseded`, `failed` |
| `Visibility` | `staged`, `active`, `inactive` |
| `BlockKind` | `paragraph`, `heading`, `list_item`, `table`, `code`, `other` |
| `DistanceMetric` | `cosine`, `dot`, `euclid` |

`BlockKind` and `DistanceMetric` are additions to the minimum enum set. The language is the result of later detection, not a required manual input. `mixed` and `unknown` are first-class values. Documents are never translated automatically.

## 4. Domain models

All models are frozen Pydantic v2 models that forbid extra fields and hide input values in validation errors. Text values that must be non-empty must also contain a non-whitespace character.

| Model | Fields | Invariants |
| --- | --- | --- |
| `DocumentRecord` | `document_id`, `created_at`, `active_version: int \| None`, `active_index_generation_id: UUID \| None`, `deleted_at: datetime \| None` | `active_version` and `active_index_generation_id` are both set or both `None`. A deleted document has neither. The repository additionally guarantees that the active generation belongs to an existing version. |
| `DocumentVersion` | `document_id`, `version`, `content_sha256`, `source_name`, `media_type`, `storage_key`, `created_at` | `version ≥ 1`. Valid SHA-256. `storage_key` is relative and opaque. `source_name` is a base name without path separators or control characters, at most 255 characters. `media_type` is a lowercase `type/subtype`. |
| `IndexGeneration` | `generation_id`, `document_id`, `document_version`, `pipeline_fingerprint`, `state`, `created_at` | `document_version ≥ 1`. Valid fingerprint. Bound to one version and one pipeline snapshot. |
| `IngestionJob` | `job_id`, `job_type`, `document_id`, `document_version: int \| None`, `index_generation_id: UUID \| None`, `status`, `stage: JobStage \| None`, `attempt`, `created_at`, `updated_at`, `error_code: str \| None` | `attempt ≥ 0`. `processing` requires a stage. `queued` and `completed` have no stage. `processing`, `completed`, and `failed` require `attempt ≥ 1`. `error_code` is set exactly when `failed` and must be a known `ING_*` code. `ingest` and `reindex` require `document_version`. `updated_at ≥ created_at`. |
| `SourceSpan` | `start_offset: int \| None`, `end_offset: int \| None`, `locator: str \| None` | Offsets are both set or both `None`, `0 ≤ start ≤ end`. At least one field is set. Recorded only when the parser produces it reliably. |
| `ExtractedBlock` | `block_index`, `text`, `kind`, `page: int \| None`, `section_path: tuple[str, ...]`, `source_span: SourceSpan \| None` | `block_index ≥ 0`. Text is non-blank. `page ≥ 1`. A missing page is `None`, never an invented `1`. |
| `ExtractionResult` | `document_id`, `document_version`, `parser_id`, `parser_version`, `blocks`, `warnings: tuple[str, ...]` | `document_version ≥ 1`. Block indexes are consecutive from 0 in order. Warnings are stable codes, never document text. An empty block tuple is allowed and handled by a later validator. |
| `DocumentChunk` | `chunk_id`, `document_id`, `document_version`, `index_generation_id`, `chunk_index`, `text`, `token_count`, `language`, `page_start`, `page_end`, `section_path`, `content_sha256`, `chunker_version` | `chunk_index ≥ 0`. `token_count > 0`. Non-blank text. Pages are both set or both `None`, `page_start ≥ 1`, `page_end ≥ page_start`. `content_sha256` equals the SHA-256 of the UTF-8 text. `chunk_id` equals the deterministic ID derived from the other fields. |
| `EmbeddingModelInfo` | `model_id`, `dimension`, `distance_metric` | Non-blank model ID. `dimension > 0`. |
| `EmbeddingResult` | `chunk_id`, `model_id`, `vector: tuple[float, ...]`, `dimension` | Non-empty vector. `dimension == len(vector)`. Every element is finite. |
| `VectorPointPayload` | `schema_version`, `document_id`, `document_version`, `index_generation_id`, `chunk_id`, `chunk_index`, `text`, `language`, `source_name`, `page_start`, `page_end`, `section_path`, `embedding_model_id`, `visibility` | `schema_version` is required. JSON-compatible values only. Same page rules as the chunk. |
| `VectorPoint` | `point_id`, `vector`, `payload` | `point_id` equals `payload.chunk_id`. The vector is finite. |
| `WriteReceipt` | `index_generation_id`, `point_count` | `point_count ≥ 0`. |
| `IndexVerification` | `index_generation_id`, `expected_count`, `found_count` | Counts ≥ 0. `is_complete` is true when the counts match. |

`dimension` is never a hard-coded constant. It comes from `EmbeddingModelInfo` after a model is selected.

## 5. State transition validation

Pure domain functions, no I/O:

- `validate_job_transition(current, target)` raises `IngestionInvalidStateError` unless the edge is in the allowed set from [architecture §6](architecture.md#6-job-state-machine).
- `transition_job(job, target, *, now, stage=None, error_code=None)` returns a new `IngestionJob`. It applies the attempt, stage, and error-code rules: a claim increments `attempt`, `completed` and `queued` clear the stage, `failed` keeps the stage and requires an error code, leaving `failed` clears the error code.
- `validate_generation_transition(current, target)` allows `staged → active`, `staged → failed`, and `active → superseded`. `failed` and `superseded` are terminal. A rollback creates a new generation.

## 6. Ports

Ports describe meaning with typed input and output. They are not SDK method lists. I/O ports are asynchronous. CPU-bound steps (extract, normalize, chunk) are synchronous so no fake asynchrony is imposed. Adapters translate vendor exceptions into the errors in §7. No vendor exception reaches the API layer.

General rules: `extract` and `chunk` never mutate their inputs and return a stable order. `VectorIndex` writes indexed points and is not the authoritative store of the document lifecycle. `SourceDocumentStore` never accepts a user-chosen absolute path. Every port must be testable with a fake and without Qdrant, model downloads, or network.

### 6.1 `DocumentRepository` (`application/ports/ingestion/documents.py`)

| Method | Meaning | Errors |
| --- | --- | --- |
| `create(document)` | Persist a new document. | `ING_CONFLICT` if it exists |
| `get(document_id)` | Return the record. | `ING_NOT_FOUND` |
| `add_version(version)` | Persist a version. Versions are consecutive. | `ING_NOT_FOUND`, `ING_CONFLICT` |
| `get_version(document_id, version)` | Return a version. | `ING_NOT_FOUND` |
| `add_generation(generation)` | Register a `staged` generation before indexing, so cleanup can find it. | `ING_NOT_FOUND`, `ING_CONFLICT` |
| `set_generation_state(generation_id, state)` | Move a generation along the allowed transitions. | `ING_NOT_FOUND`, `ING_INVALID_STATE` |
| `get_active(document_id)` | Return the active generation or `None`. Used by Retrieval. | `ING_NOT_FOUND` |
| `publish_generation(generation_id, *, expected_active_generation_id)` | Compare-and-set the active pointer, mark the new generation `active` and the predecessor `superseded`. | `ING_CONFLICT` on CAS mismatch, `ING_INVALID_STATE` |
| `mark_deleted(document_id, *, deleted_at)` | Set `deleted_at` and clear the active pointer. Idempotent. | `ING_NOT_FOUND` |

`add_generation`, `get_version`, and `set_generation_state` extend the mandatory operation set. They are needed for crash recovery and cleanup.

### 6.2 `SourceDocumentStore` (`documents.py`)

| Method | Meaning |
| --- | --- |
| `put(content: bytes) -> str` | Store bytes via temporary write plus finalize. Returns a generated opaque `storage_key`. |
| `get(storage_key) -> bytes` | Return the stored bytes. `ING_NOT_FOUND` if missing. |
| `delete(storage_key)` | Remove the source. Idempotent. |

### 6.3 `IngestionJobRepository` (`jobs.py`)

| Method | Meaning |
| --- | --- |
| `enqueue(job, *, idempotency_key, request_fingerprint)` | Create a queued job. The same key and fingerprint returns the stored job. The same key with another fingerprint raises `ING_CONFLICT`. |
| `get(job_id)` | Return the job. `ING_NOT_FOUND`. |
| `claim(*, worker_id, lease_seconds, now)` | Atomically move one queued job to `processing`, increment `attempt`, set the lease. Returns `None` when nothing is claimable. |
| `heartbeat(job_id, *, attempt, lease_seconds, now)` | Extend the lease. `ING_CONFLICT` if the attempt is stale. |
| `record_stage(job_id, *, attempt, stage, now)` | Record the current stage. |
| `complete(job_id, *, attempt, now)` | `processing → completed`. |
| `fail(job_id, *, attempt, error_code, now)` | `processing → failed`, keeping the stage. |
| `requeue(job_id, *, now)` | Explicit retry, `failed → queued`. |
| `release_expired(*, now)` | Move expired `processing` jobs to `queued`. Returns the released job IDs. |

The SQLite adapter (ING-006) implements the atomic claim, the attempt compare-and-swap, the lease, and the attempt history. The worker loop, lease renewal, and retry policy are ING-019–020. Adapter behavior beyond these signatures is described in [intake and persistence](intake-and-persistence.md).

### 6.4 Processing ports

| Port (file) | Method | Meaning |
| --- | --- | --- |
| `DocumentExtractor` (`extract.py`) | `supports(media_type) -> bool` | Whether the extractor handles the type. |
| | `extract(*, document_id, document_version, source_name, media_type, content) -> ExtractionResult` | Raises `ING_UNSUPPORTED_MEDIA_TYPE`, `ING_INVALID_DOCUMENT`, or `ING_EXTRACTION_FAILED`. |
| `TextNormalizer` (`transform.py`) | `normalize(result) -> tuple[ExtractedBlock, ...]` | Preserves locators. |
| `DocumentChunker` (`transform.py`) | `chunk(blocks, *, document_id, document_version, index_generation_id, language) -> tuple[DocumentChunk, ...]` | Ordered and reproducible. Raises `ING_INVALID_CHUNK`. |
| `EmbeddingProvider` (`embedding.py`) | `describe_model() -> EmbeddingModelInfo` | Model identity and dimension. |
| | `embed_documents(chunks) -> tuple[EmbeddingResult, ...]` | Document mode. Raises `ING_EMBEDDING_UNAVAILABLE`. |
| | `embed_query(text) -> tuple[float, ...]` | Query mode, separate from document mode. Model-specific prefixes belong to the provider. |
| `VectorIndex` (`vectors.py`) | `ensure_compatible(model, *, payload_schema_version)` | Raises `ING_INDEX_INCOMPATIBLE` on any mismatch. Never converts silently. |
| | `upsert(points) -> WriteReceipt` | Idempotent. Raises `ING_VECTOR_STORE_UNAVAILABLE`. |
| | `set_visibility(document_id, index_generation_id, visibility) -> WriteReceipt` | Payload update. |
| | `delete_generation(document_id, index_generation_id) -> WriteReceipt` | Remove exactly one generation. |
| | `verify(document_id, index_generation_id, expected_point_ids) -> IndexVerification` | Read back counts. A failure never returns a false success. |

## 7. Error contract

Domain and application code raise `IngestionError` subclasses with a stable machine code and a `retryable` flag. They never raise `HTTPException`. The error carries no document text, stack trace, raw parser or provider error, local path, or secret.

| Code | Meaning | Retry default |
| --- | --- | --- |
| `ING_UNSUPPORTED_MEDIA_TYPE` | Unsupported content type | no |
| `ING_FILE_TOO_LARGE` | File size limit | no |
| `ING_INVALID_DOCUMENT` | Corrupt or unreadable source | no |
| `ING_EXTRACTION_FAILED` | Parser cannot extract valid content | no, unless an explicit transient dependency |
| `ING_INVALID_CHUNK` | Normalization or chunk invariant violated | no |
| `ING_EMBEDDING_UNAVAILABLE` | Transient embedding service failure | yes, bounded |
| `ING_VECTOR_STORE_UNAVAILABLE` | Transient Qdrant failure | yes, bounded |
| `ING_CONFLICT` | Idempotency, concurrency, or state conflict | only after an explicit re-read |
| `ING_NOT_FOUND` | Unknown document or job | no |
| `ING_INVALID_STATE` | Forbidden lifecycle transition | no |
| `ING_INDEX_INCOMPATIBLE` | Collection does not match model, dimension, metric, or payload schema | no |
| `ING_INTERNAL_ERROR` | Unclassified internal error | by policy, never automatic |

`ING_INDEX_INCOMPATIBLE` is an addition to the minimum taxonomy. Without it a collection mismatch would have to hide inside `ING_CONFLICT`. The class attribute `retryable` is `True` only for the two availability codes. `ING_CONFLICT` and `ING_INTERNAL_ERROR` are `False` because their retry needs a decision.

The later FastAPI adapter maps these into the unchanged Foundation envelope:

```json
{
  "error": {
    "code": "ING_INVALID_DOCUMENT",
    "message": "The document could not be processed",
    "details": null
  },
  "request_id": "generated-request-id"
}
```

The final status table belongs to ING-022–024. The Foundation 404, 405, 422, and 500 conventions stay. Ingestion 415, 409, and 413 responses are introduced only with a documented, tested mapping.
