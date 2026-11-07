# Ingestion configuration

Status: implemented by PR-ING-002 in `core/config.py` (fields are the lower-case names of the variables below, for example `ingestion_enabled`). `.env.example` lists every field. Ingestion settings extend the existing Foundation `Settings` in `core/config.py`. No second settings class or resolver is introduced.

## 1. Source priority

The Foundation priority is kept:

1. Explicit settings or app factory injection.
2. Process environment.
3. Repository-root `.env`.
4. Safe defaults.

The root `.env` path is not resolved from the working directory. Unknown `.env` keys that belong to other components do not cause errors. Tests that pass explicit settings do not read a developer's personal `.env`.

## 2. Settings

These defaults are new ingestion decisions, not values taken from the Foundation.

| Variable | Type | Default and validation |
| --- | --- | --- |
| `INGESTION_ENABLED` | bool | `false`. May be enabled only when a working pipeline exists. |
| `INGESTION_STORAGE_ROOT` | absolute path | `<repo root>/data/ingestion/sources`. Not created at import or settings initialization. |
| `INGESTION_DB_PATH` | absolute path | `<repo root>/data/ingestion/registry.sqlite3`. No connection at import or settings initialization. |
| `INGESTION_MAX_FILE_BYTES` | int > 0 | `26214400` (25 MiB). |
| `INGESTION_ALLOWED_EXTENSIONS` | JSON list | `[".txt", ".md", ".pdf", ".docx"]`. Lower case, leading dot, subset of the supported set. An extension alone is not sufficient validation. |
| `INGESTION_MAX_CONCURRENT_JOBS` | int > 0 | `1`. |
| `INGESTION_JOB_LEASE_SECONDS` | int > 0 | `300`. Used by the later worker. |
| `INGESTION_CHUNK_TARGET_TOKENS` | int > 0 | `400`. Initial baseline, to be benchmarked. |
| `INGESTION_CHUNK_OVERLAP_TOKENS` | int ≥ 0 | `64`. Always lower than the target. |
| `INGESTION_EMBEDDING_PROVIDER` | enum | `none` until a provider is implemented and selected. |
| `INGESTION_EMBEDDING_MODEL` | str or unset | Unset until a baseline model is selected. |
| `INGESTION_EMBEDDING_BATCH_SIZE` | int > 0 | `16`. Measurable later. |
| `INGESTION_QDRANT_COLLECTION` | safe name | `rag_chunks_v1`. Matches `[A-Za-z][A-Za-z0-9_-]{0,62}`. |
| `INGESTION_ALLOW_REMOTE_EMBEDDING` | bool | `false`. External data transfer only with explicit opt-in. |

Relative path values are resolved against the repository root, never the working directory. Outside a source checkout, where no repository root exists, the path defaults are unset and any explicit value must be absolute.

`QDRANT_URL` and `QDRANT_TIMEOUT_SECONDS` stay the shared Foundation settings. No ingestion-specific Qdrant host configuration is created. The chunk configuration does not guarantee the embedding model's maximum input size. Tokenizer and limit compatibility is checked by ING-011 and ING-013–015.

## 3. Cross-field validation

- `INGESTION_CHUNK_OVERLAP_TOKENS` must be lower than `INGESTION_CHUNK_TARGET_TOKENS`.
- With `INGESTION_ENABLED=true`, an embedding provider other than `none` and an embedding model are required, and both storage paths must be known. The only provider value today is `none`, so enabling ingestion is rejected until ING-013–015 adds a provider. This is intentional: ingestion is never silently enabled with a non-viable configuration.
- A remote provider additionally requires `INGESTION_ALLOW_REMOTE_EMBEDDING=true` when providers are added.

PR-ING-002 performs static validation only. It does not contact Qdrant, download a model, or touch the SQLite file. Anything that needs the real component is checked when that component is wired in.

## 4. Security and operations

- Raw document text, unnecessary filename detail, and upload bodies are not logged.
- Storage keys are generated. Paths from users are never concatenated.
- Real content validation is part of ING-004.
- Document data reaches an external provider only with explicit configuration and documented data handling.
- `data/ingestion/` holds local data and is not version controlled. `.gitignore` already covers `*.sqlite3`. PR-ING-002 adds `data/ingestion/` because the source store directory is not covered today.
- The full `Settings` object is never serialized or logged. Later secret keys use `SecretStr`.
- No new logger or Docker service is added.

## 5. Test matrix

| Case | Expected |
| --- | --- |
| Ingestion disabled, no `.env` | Foundation API starts. |
| `INGESTION_MAX_FILE_BYTES=0` | Validation error. |
| Overlap ≥ target | Validation error. |
| `INGESTION_MAX_CONCURRENT_JOBS=0` | Validation error. |
| Invalid collection name | Validation error. |
| Process environment vs root `.env` | Process environment wins. |
| Different working directory | Same root `.env` resolution. |
| Explicit test settings | No personal `.env` read. |
| Unknown root `.env` key | No startup error. |
| Enabled with no provider or model | Validation error, never silently enabled. |

## 6. Provenance and downstream impact

| Setting group | Origin | Downstream tasks |
| --- | --- | --- |
| Paths, file limits, extensions | ADR-ING-001 | ING-004–006 |
| Concurrency, lease | ADR-ING-001 | ING-019–020 |
| Chunk sizes | Initial baseline | ING-011–012 |
| Embedding provider, model, batch, remote opt-in | Open decision | ING-013–015 |
| Qdrant collection | ADR-ING-003 | ING-016–018, 03 Retrieval |

No migration is needed. Existing deployments get safe defaults and a disabled pipeline.
