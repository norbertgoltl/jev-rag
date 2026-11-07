# Document Ingestion architecture

Status: accepted design for ING-001. Companion documents: [contracts](contracts.md), [configuration](configuration.md), [retrieval handoff](retrieval-handoff.md), and the ADRs [ING-001](adr/ADR-ING-001-persistence-and-worker.md), [ING-002](adr/ADR-ING-002-identities-and-idempotency.md), [ING-003](adr/ADR-ING-003-index-publication.md).

This document is design only. It adds no endpoint, adapter, migration, parser, or worker. Everything marked "later" is implemented in the ING task named next to it.

## 1. Scope and Foundation constraints

The ingestion design extends the existing Foundation package (`apps/api`, `src/jev_rag_api`) and reuses its app factory, `Settings`, error envelope, `X-Request-ID`, and JSON logging. It introduces no second FastAPI app, Python project, settings mechanism, or logger. Foundation endpoints and contracts are unchanged.

The decisions below are new ingestion decisions recorded in the ADRs. The Foundation does not already make them.

## 2. Layers and dependency direction

| Layer | Responsibility | May import |
| --- | --- | --- |
| API | Input, access protection, HTTP status, response envelope, domain error to HTTP mapping. Routes belong to ING-022–024. | application, domain |
| Application | Use cases, job lifecycle, step ordering, retry and recovery coordination. Uses infrastructure only through ports. | domain, ports |
| Domain | Document and job identity, state transitions, metadata invariants, domain errors. | standard library, Pydantic |
| Ports | Typed abstractions toward the filesystem, SQLite, parsers, the embedding provider, and Qdrant. No concrete SDK dependency. | domain |
| Integrations | Concrete adapters, each in its own later ING task. | everything inward |

Domain and application code must not import `fastapi`, `qdrant_client`, a SQLite adapter, a PDF or DOCX parser, a provider SDK, or Jev types. The HTTP layer uses only the public use case contract. The Jev Decision Layer is outside this block.

## 3. Processing data flow

```text
HTTP intake (ING-022)
  └─ validation + persisted source + document identity (ING-004–006)
       └─ durable queued job (ING-019)
            └─ extraction (ING-007–009)
                 └─ normalization (ING-010)
                      └─ chunking + provenance (ING-011–012)
                           └─ embedding (ING-013–015)
                                └─ staged Qdrant points (ING-016–017)
                                     └─ activation + cleanup (ING-018)
                                          └─ job completed (ING-019–021)
```

`completed` is set only after the index write has been verified and the publication and finalization steps have succeeded. An HTTP 202 means only that a job was durably created. It does not mean successful processing.

## 4. Components

| Component | Input → output | Exclusive responsibility | Implemented in |
| --- | --- | --- | --- |
| Intake | file + request metadata → document version + job | Validation, persistence, identification | ING-004–006, 022 |
| Extractor | document source → `ExtractionResult` | Preserve structure and source location | ING-007–009 |
| Normalizer | `ExtractionResult` → normalized blocks | Meaning-preserving text cleanup | ING-010 |
| Chunker | normalized blocks → `DocumentChunk[]` | Token limit, order, provenance | ING-011–012 |
| Embedder | chunks → `EmbeddingResult[]` | Model identity, dimension check | ING-013–015 |
| VectorIndex | embeddings + payload → write receipt | Idempotent write, delete, index verification | ING-016–018 |
| Registry | document, job, generation → durable state | CAS and concurrency, recovery | ING-005–006 |
| Orchestrator and worker | queued job → terminal state | Step order, retry, finalization | ING-019–021 |
| API adapter | HTTP request → use case | Foundation error envelope, correlation | ING-022–024 |

Qdrant is not the document registry. A Qdrant payload never replaces the durable record of the source document.

### Step input and output

| Step | Input | Output | Failure result |
| --- | --- | --- | --- |
| Validate | stored source, declared media type, size | accepted source or error | `ING_UNSUPPORTED_MEDIA_TYPE`, `ING_FILE_TOO_LARGE`, `ING_INVALID_DOCUMENT` |
| Extract | source bytes | `ExtractionResult` | `ING_EXTRACTION_FAILED`, `ING_INVALID_DOCUMENT` |
| Normalize | `ExtractionResult` | blocks with preserved locators | `ING_INVALID_CHUNK` |
| Chunk | blocks, document identity, generation id, language | ordered `DocumentChunk` tuple | `ING_INVALID_CHUNK` |
| Embed | chunks | `EmbeddingResult` per chunk | `ING_EMBEDDING_UNAVAILABLE` (retry) |
| Index | embeddings + `VectorPointPayload` | staged points, write receipt | `ING_VECTOR_STORE_UNAVAILABLE` (retry), `ING_INDEX_INCOMPATIBLE` |
| Finalize | verified staged generation | active generation, superseded predecessor | `ING_CONFLICT`, `ING_INVALID_STATE` |

## 5. Document, version, and generation lifecycle

Three distinct concepts are used. They must never be conflated.

| Concept | Meaning | Created when |
| --- | --- | --- |
| `Document` | Durable logical identity (`document_id`). The same file content can be registered as two separate documents. | A new upload creates a new document. |
| `DocumentVersion` | The concrete source bytes of one document (`document_version`, `content_sha256`). Tied to a source change. | The source content of an existing document changes. |
| `IndexGeneration` | The index representation of one document version under a specific parser, normalizer, chunker, tokenizer, embedding model, and vector schema (`pipeline_fingerprint`). | A first ingest, a changed pipeline configuration, or an explicit `force_reindex`. |

A new model or chunker produces a new generation for the same version without a new document version. Identity rules are specified in [ADR-ING-002](adr/ADR-ING-002-identities-and-idempotency.md) and [contracts](contracts.md).

### Lifecycle scenarios

| Scenario | Document | Version | Generation | Job |
| --- | --- | --- | --- | --- |
| First upload | new | 1 | new, `staged` then `active` | `ingest` |
| Duplicate upload (same idempotency key and fingerprint) | existing | unchanged | unchanged | the original job is returned |
| Same idempotency key, different content | existing | unchanged | unchanged | `ING_CONFLICT`, nothing created |
| Same hash, different document | new | 1 | new | `ingest`, no automatic merge |
| Changed source for an existing document | existing | +1 | new | `ingest` |
| Unchanged source and unchanged fingerprint | existing | unchanged | unchanged | no new version, no new points |
| Pipeline change (model, chunker) | existing | unchanged | new | `reindex` |
| `force_reindex` | existing | unchanged | new | `reindex` |
| Delete | existing, `deleted_at` set | unchanged | all deactivated, then removed | `delete` |

## 6. Job state machine

`JobStatus`: `queued`, `processing`, `completed`, `failed`. `JobStage` during processing: `validating`, `extracting`, `normalizing`, `chunking`, `embedding`, `indexing`, `finalizing`. `JobType`: `ingest`, `reindex`, `delete`.

| Transition | Condition |
| --- | --- |
| `queued → processing` | Durable claim by exactly one worker. Opens a new attempt (`attempt` increases by one). |
| `processing → completed` | Every mandatory operation and the publication are confirmed. |
| `processing → failed` | Permanent error or exhausted retry budget. |
| `processing → queued` | Only for a documented durable recovery or retry decision (lease expiry, bounded transient retry). |
| `failed → queued` | Explicit retry. History is preserved. The next claim opens a new attempt. |

All other transitions are forbidden, including every transition out of `completed` and `completed → processing` within an attempt. A re-run after completion is a new job.

`completed` and `failed` are terminal for one attempt. A retry opens a new attempt and never deletes earlier error diagnostics. The attempt number is also the fencing token: a worker that lost its lease cannot update the job with a stale attempt.

Stage rules: `processing` requires a stage. `queued` and `completed` carry no stage. `failed` keeps the failing stage for diagnostics. `error_code` is set only on `failed`.

### Concurrency

At most one operation that publishes an active index may run for one `document_id` at a time. Different documents may be processed in parallel. The SQLite design must provide atomic claim (CAS) and lease expiry. The mechanism is implemented in ING-019–020. The contract is fixed here and in [ADR-ING-001](adr/ADR-ING-001-persistence-and-worker.md).

## 7. Durable state and atomic boundaries

- The source file, the registry, and Qdrant are three separate state spaces. No database transaction spans them.
- The source file is saved with a safe temporary write plus finalize pattern. A registry record may reference only a preserved source instance.
- Qdrant writes are idempotent with stable point identifiers. After a partial write the step can be repeated or compensated.
- The registry is the authoritative source of the active document version and index generation. The Qdrant `visibility` field is a search optimization and a transient-state marker. It is not the final validity decision.
- Switching the active pointer and updating Qdrant payloads are not atomic. Retrieval therefore also verifies the registry's active generation. Otherwise it could return an old chunk temporarily. See the [retrieval handoff](retrieval-handoff.md).
- Physical cleanup and logical publication are separate operations. A failed cleanup leaves a diagnosable, retryable state.

**Baseline limit:** there is no guaranteed zero-overlap atomic version switch across several stores. The reader-side check above is the mitigation and is a mandatory retrieval requirement.

## 8. Failure points and recovery

| Failure point | Planned behavior |
| --- | --- |
| Validation or extraction | Unsupported or corrupt source: permanent failure, no index publication. |
| Normalization or chunking | Contract or content error: permanent failure, source preserved. |
| Embedding service | Timeout or transient service failure: bounded retry. |
| Qdrant partial upsert | Repeat the operation with the same stable point IDs, or delete exactly the staged points of the generation. |
| Worker interrupted | Recovery by expired lease, same generation. |
| Failure during publication | The registry's active pointer stays authoritative. A half-built generation is never treated as active. |
| Cleanup failed | A trackable cleanup-pending state remains. A failed cleanup is never reported as success and no data is lost silently. |
| Delete interrupted | The delete workflow is re-runnable. A deleted document must not be retrievable at any point after `mark_deleted`. |

### Recovery rules in detail

1. **Duplicate upload.** The registry stores the idempotency key with the request fingerprint. A repeated pair returns the stored job. A repeated key with a different fingerprint is `ING_CONFLICT`.
2. **Partial Qdrant write.** Point IDs are deterministic UUIDv5 values derived from the generation. A retry upserts the same IDs. `verify` compares expected and stored point counts before activation.
3. **Worker crash.** A heartbeat extends the lease. `release_expired` moves expired `processing` jobs back to `queued`. The next claim reuses the same `index_generation_id` recorded on the job, so staged points are overwritten and not duplicated.
4. **Publication failure.** Activation first writes the registry pointer (compare-and-set against the expected previous generation), then sets Qdrant visibility. If the Qdrant step fails, retrieval still filters by the registry. A reconcile step repeats the visibility update.
5. **Deletion.** `mark_deleted` is committed first. After that the document is excluded by the registry check. Qdrant points and the source file are removed by a re-runnable cleanup. Failure keeps the document in a cleanup-pending state.

## 9. Security and operations

- Raw document text, unnecessary filename details, and upload bodies never reach the Foundation JSON log. Logs carry `document_id`, `job_id`, stage, and error code only.
- Storage keys are generated. They are never user paths. No path traversal and no unbounded temporary files.
- The media type is validated on real content in ING-004, not only by extension.
- Document data goes to an external embedding provider only with explicit configuration and documented data handling.
- Local database and source store paths are not version controlled (see [configuration](configuration.md)).
- No second logger or framework and no new Docker service are introduced.
- The full `Settings` object is never serialized or logged. Future secret keys use a secret type.

## 10. Dependency map

| Block | Depends on this design for |
| --- | --- |
| ING-004–006 intake, source store, SQLite registry | models, state transitions, repository and store ports, ADR-ING-001/002 |
| ING-007–012 parser, normalizer, chunker | extraction, transform ports, provenance fields |
| ING-013–018 embedding, Qdrant, publication | embedding and vector ports, payload schema, ADR-ING-003 |
| ING-019–024 worker, retry, HTTP API | job state machine, error taxonomy, idempotency |
| 03 Retrieval | active generation rule and payload schema |

No adapter is implemented ahead of its block.

## 11. Open decisions

Only decisions that do not block the typed contracts of PR-ING-002 remain open.

| Decision | Owner | Why it does not block |
| --- | --- | --- |
| Concrete embedding model, dimension, tokenizer | ING-013–015 | `dimension` is data, not a constant. Settings default to provider `none`. |
| Embedding query and document prefixes | ING-013–015 | Part of the provider contract, behind `embed_query` and `embed_documents`. |
| Final HTTP status table for ingestion errors | ING-022–024 | Domain errors carry stable codes only. |
| Qdrant payload indexes | ING-016–017 | The payload fields are fixed. Index selection follows measured filters. |
| Chunk size tuning | ING-011 | Initial 400 tokens and 64 overlap are baselines. |
| Cleanup retention and garbage-collection schedule | ING-018 | The cleanup-pending state exists in the contract. |
