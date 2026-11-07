# ADR-ING-001 – Persistence and worker

Status: accepted (pending reviewer sign-off at the PR-ING-001 merge gate). Related tasks: ING-001, ING-003. Consumers: ING-004–006, ING-019–021.

## Context

Ingestion needs durable document and job state, original source preservation, and background processing. [ADR-001](../../adr/ADR-001-vector-store.md) makes Qdrant a rebuildable search index and states that original documents and processing configuration must be preserved separately. The project runs applications on the host and keeps Docker limited to infrastructure services. There is one writer process and no cross-host coordination requirement.

## Decision

- **Registry:** SQLite in a local durable file (`INGESTION_DB_PATH`). It stores documents, versions, index generations, jobs, attempts, and idempotency keys. No separate database service.
- **Source store:** a configurable local directory (`INGESTION_STORAGE_ROOT`), separate from the versioned registry record. Registry rows reference sources by a generated opaque `storage_key`.
- **Worker:** a separate host process managed by `uv`, not a FastAPI request background task. It claims jobs from the registry.
- **Job claim:** an atomic claim (compare-and-set on status and attempt) with a lease of `INGESTION_JOB_LEASE_SECONDS`. A heartbeat extends the lease. Expired leases are released back to `queued`.
- **Concurrency:** at most one active-index-publishing operation per `document_id`. Different documents may run in parallel up to `INGESTION_MAX_CONCURRENT_JOBS`, default 1.
- **Source write:** temporary file plus finalize (atomic rename in the same directory). The registry row is written only after the source is preserved.

## Crash recovery

| Crash point | Result |
| --- | --- |
| Before the source is finalized | No registry row exists. The temporary file is orphaned and removed by cleanup. |
| After the source, before the registry row | An orphan source file exists. Cleanup removes unreferenced keys. |
| Worker dies while processing | The lease expires, `release_expired` returns the job to `queued`, the next claim reuses the same generation. |
| Registry written, Qdrant partial | Retry upserts stable point IDs. See [ADR-ING-003](ADR-ING-003-index-publication.md). |

## Alternatives considered

| Alternative | Why not now |
| --- | --- |
| PostgreSQL in Docker | Adds a failure domain and a service with no current need. [ADR-001](../../adr/ADR-001-vector-store.md) already allows adding it later if relational needs dominate. |
| Redis or a message broker queue | One writer, state must survive restarts anyway, and the registry already provides durability. A broker adds a second durable store to keep consistent. |
| FastAPI `BackgroundTasks` | Tied to the request process lifetime. A restart loses work. No lease or recovery. |
| Store sources in Qdrant or the database | Qdrant is a rebuildable index. Large blobs in SQLite complicate backup and growth. |
| In-process thread pool | No isolation from the API process, no recovery after a crash. |

## Consequences

- Backup means the SQLite file plus the source directory. Both live under `data/ingestion/` by default and are not version controlled.
- SQLite allows one writer at a time. Throughput is bounded and sufficient for the local baseline.
- The ports (`DocumentRepository`, `IngestionJobRepository`, `SourceDocumentStore`) keep the application independent of SQLite, so a later migration changes adapters only.
- No new infrastructure or Docker service is introduced.

## Reconsideration triggers

Revisit if multiple hosts need to process jobs, if write contention on SQLite becomes measurable, if relational requirements such as users or access control grow, or if source volume makes a local directory impractical.
