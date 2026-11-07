# ADR-ING-002 – Identities and idempotency

Status: accepted (pending reviewer sign-off at the PR-ING-001 merge gate). Related tasks: ING-001, ING-002, ING-003. Consumers: ING-004–006, ING-013–018, ING-022.

## Context

Uploads can be repeated, sources can change, and the same source can be re-indexed under a new model or chunker. Without precise identities these cases get confused, which leads to duplicate points, lost history, or unwanted merges. The identity model must hold across the file store, the registry, and Qdrant, which share no transaction.

## Decision

### Identifiers

| Identifier | Rule |
| --- | --- |
| `document_id` | UUIDv4 at document creation. |
| `job_id` | UUIDv4 for every new work run. |
| `document_version` | Positive integer per document, starting at 1. |
| `index_generation_id` | UUIDv4 for every new index generation. |
| `chunk_id` and Qdrant point ID | UUIDv5 of `(document_id, document_version, index_generation_id, chunk_index, chunk content hash)` in the canonical form defined in [contracts](../contracts.md#deterministic-chunk-and-point-id). |
| `content_sha256` | SHA-256 of the source bytes for a version, of the UTF-8 text for a chunk. Lowercase hex. |
| `pipeline_fingerprint` | SHA-256 of the canonical, sorted, versioned description of parser, normalizer, chunker, tokenizer, embedding model, and relevant settings. No secrets, absolute host paths, or timestamps. |

### Role of SHA-256

The hash identifies content. It does not identify a document. The same bytes uploaded as two documents stay two documents and are never merged automatically. Within one `document_id`, the hash decides whether a source changed.

### Behavior

| Case | Outcome |
| --- | --- |
| Same idempotency key, same request fingerprint | Returns the same job and result. |
| Same idempotency key, different content | `ING_CONFLICT`. Nothing is created. |
| Unchanged source and unchanged `pipeline_fingerprint` for a `document_id` | No new version and no new points. |
| Changed source for an existing document | New `document_version`, new generation. |
| Changed pipeline, same source | New generation, same version (`reindex`). |
| `force_reindex` | Explicit operation. New generation, same version. |
| Same hash under another document | New document, no automatic merge. |

### Concurrency

At most one active-index-publishing operation runs per `document_id`. Publication uses a compare-and-set on the registry's active generation (`expected_active_generation_id`). A losing writer receives `ING_CONFLICT` and must re-read the state before any retry.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Content hash as document ID | Merges unrelated uploads, breaks per-document deletion and access scope. |
| Random point IDs | Retries create duplicate points. Partial writes cannot be repeated safely. |
| Point ID without the generation | A staged generation would overwrite the active one before publication. |
| Version number as the unit of reindex | Forces a fake source version for each model change. It mixes source change and pipeline change. |
| Global content deduplication | Silent merging across documents changes ownership and deletion semantics. Could be added later as an explicit feature. |

## Consequences

- Retrying any step reuses the same point IDs and is safe.
- Staged and active points of one document coexist without collisions.
- The namespace UUID is permanent. Changing it is a breaking migration.
- Idempotency keys and request fingerprints must be persisted with the job.
- Reindex history is visible as multiple generations for one version.

## Reconsideration triggers

Revisit if storage cost of identical files becomes material (opt-in deduplication), if cross-tenant identity rules appear, or if fingerprint inputs prove insufficient to detect a pipeline change.
