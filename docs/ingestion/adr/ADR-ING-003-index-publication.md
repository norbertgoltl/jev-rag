# ADR-ING-003 – Index publication and the registry-to-retrieval active pointer

Status: accepted (pending reviewer sign-off at the PR-ING-001 merge gate). Related tasks: ING-001, ING-002, ING-003. Consumers: ING-016–018, 03 Retrieval. Builds on [ADR-001](../../adr/ADR-001-vector-store.md).

## Context

Qdrant is a rebuildable index. The registry holds the document lifecycle. No transaction spans both, so a version switch cannot be atomic. Retrieval must not return chunks of a superseded or half-built generation, and a deleted document must not be retrievable.

## Decision

### Staged and active workflow

1. The registry records a new `IndexGeneration` in state `staged`.
2. The worker upserts points with `visibility = staged` and stable point IDs.
3. `VectorIndex.verify` compares expected and stored point counts.
4. The registry publishes the generation by compare-and-set on the active pointer. The new generation becomes `active`, the previous one `superseded`.
5. Qdrant visibility is updated: new points to `active`, old points to `inactive`.
6. Cleanup removes superseded points. This is a separate step from publication.
7. Only then does the job become `completed`.

### Authority

The registry is the authority for the active version and generation. Qdrant `visibility` is a search optimization and a transient-state marker. Retrieval verifies every hit against `DocumentRepository.get_active` (see the [retrieval handoff](../retrieval-handoff.md)). This is a mandatory requirement because steps 4 and 5 are not atomic.

### Failure handling

| Failure | Result |
| --- | --- |
| Partial upsert | Repeat with the same point IDs, or delete exactly the staged points of the generation. |
| Verification mismatch | The generation is not published. It is retried or marked `failed`. |
| CAS mismatch in step 4 | `ING_CONFLICT`. Nothing is published. |
| Failure after step 4, before step 5 | The registry is already correct and Retrieval filters by it. A reconcile step repeats the visibility update. |
| Cleanup failure | A cleanup-pending state remains and is retried. It is never reported as success. |
| Failure before step 4 | The previous active generation stays active. The staged generation is never treated as active. |
| Delete | `mark_deleted` commits first. Points and sources are removed by a re-runnable cleanup. |

### Collection compatibility

A collection is compatible when embedding model identifier, vector dimension, distance metric, and payload schema match. `VectorIndex.ensure_compatible` rejects a mismatch with `ING_INDEX_INCOMPATIBLE`. There is no silent conversion. The collection name comes from `INGESTION_QDRANT_COLLECTION`, default `rag_chunks_v1`, and the collection is created by the Qdrant adapter in ING-016, not by Foundation or by this block.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Trust Qdrant `visibility` alone | Transiently wrong between steps 4 and 5. Could return old chunks. |
| Overwrite points in place | Readers see a mix of old and new chunks during the write. No rollback. |
| One collection per generation | Many collections, harder compatibility and cleanup. Reconsider at large scale. |
| Delete old points before publishing | A failure leaves the document unsearchable. |
| Cross-store two-phase commit | Not available between SQLite and Qdrant. |

## Consequences

- A short window with both generations in Qdrant is accepted and handled on the reader side.
- Retrieval pays one registry lookup per distinct document in a result set.
- Payload and point ID rules are versioned. Changes need a migration and reindexing plan.
- Garbage collection is a distinct, observable operation.

## Reconsideration triggers

Revisit if the registry lookup becomes a measured retrieval bottleneck, if the document count makes per-generation payload updates slow, or if Qdrant gains a mechanism for atomic multi-point generation switching that fits the deployment.
