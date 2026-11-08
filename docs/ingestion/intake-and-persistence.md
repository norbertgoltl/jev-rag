# Document intake and persistence

Status: implemented by PR-ING-003 (ING-004) and PR-ING-004 (ING-005, ING-006). Contracts are unchanged: see [contracts](contracts.md). Decisions: [ADR-ING-001](adr/ADR-ING-001-persistence-and-worker.md), [ADR-ING-002](adr/ADR-ING-002-identities-and-idempotency.md), [ADR-ING-003](adr/ADR-ING-003-index-publication.md).

All adapters live in `apps/api/src/jev_rag_api/integrations/ingestion/`. None of them runs at import time or when `Settings` is created. Directories, files, and connections appear only after an explicit `initialize()` or `connect()` call.

| Module | Task | Responsibility |
| --- | --- | --- |
| `content_validation.py` | ING-004 | Bounded, content-based validation of source bytes |
| `local_source_store.py` | ING-005 | `SourceDocumentStore` on the local filesystem |
| `sqlite_database.py` | ING-006 | Connection lifecycle, versioned migrations, error mapping |
| `sqlite_documents.py` | ING-006 | `DocumentRepository` |
| `sqlite_jobs.py` | ING-006 | `IngestionJobRepository` |

## 1. Input validation (ING-004)

`DocumentContentValidator(max_file_bytes=..., allowed_extensions=...)` is synchronous and pure. `validate(source_name=, source=, declared_media_type=, declared_size=)` returns an adapter-local `ValidatedDocument` (bytes, size, SHA-256 of the original bytes, canonical media type, source name). It adds no domain model, route, or storage.

Order of checks:

1. File name: must satisfy the domain `SourceName` rules, otherwise `ING_INVALID_DOCUMENT`. The extension must be in the configured allowlist, otherwise `ING_UNSUPPORTED_MEDIA_TYPE`. The name is metadata only and never reaches a path.
2. Declared media type: `application/octet-stream` or none is accepted. A type that does not match the extension raises `ING_UNSUPPORTED_MEDIA_TYPE`. Parameters such as `charset` are ignored.
3. Size: `declared_size` above the limit is rejected early, but only the bytes actually read are authoritative. Streams are read in 64 KiB chunks and never beyond `max_file_bytes + 1`. Over the limit raises `ING_FILE_TOO_LARGE`. Zero bytes raises `ING_INVALID_DOCUMENT`.
4. Content, by extension. A mismatch between extension and real content raises `ING_INVALID_DOCUMENT`.

| Extension | Media type | Content rules |
| --- | --- | --- |
| `.txt` | `text/plain` | Strict UTF-8 with optional BOM. No NUL, no C0 control characters except tab, LF, FF, CR, no DEL. Must contain visible text. UTF-16 and legacy code pages are rejected. ING-008 must use the same policy or update this document. |
| `.md` | `text/markdown` | Same rules as `.txt`. `text/x-markdown` and `text/plain` are accepted as declared types. |
| `.pdf` | `application/pdf` | `%PDF-` header, `%%EOF` in the last 1024 bytes, `startxref` in the last 2048 bytes, then `pypdf` (`strict=False`) must open the file, it must not be encrypted, and the page tree must have 1 to 10,000 pages with a resolvable first page. |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Valid ZIP, see below. |

### PDF limits and trade-offs

The check proves that the cross-reference data and page tree are readable. It does not extract text, run OCR, or validate content streams, fonts, or images. `pypdf` runs in tolerant mode so that slightly damaged but common files keep working. The `%%EOF` and `startxref` window checks therefore carry the truncation detection. A legitimate PDF with more than 1 KiB of trailing garbage after `%%EOF` is rejected. Password-protected files are rejected because ING-007–009 could not read them either.

`pypdf>=7.0.0,<8` is a new runtime dependency. It is pure Python and works on CPython 3.14. `uv.lock` was updated intentionally.

### DOCX limits

The archive is never extracted to disk. Declared sizes in ZIP headers are not trusted, so every entry is decompressed in chunks and counted.

| Limit | Value |
| --- | --- |
| Entries | 2,000 |
| Entry name length | 255 characters |
| Uncompressed size per entry | 128 MiB |
| Uncompressed size in total | 256 MiB |
| Compression ratio | 200:1, applied to entries of 1 MiB or more |
| Compression methods | stored and deflate only |

Rejected: encrypted entries, duplicate names (case-insensitive), absolute names, `..` segments, drive prefixes, backslashes, NUL, and `word/vbaProject.bin`. Required: `[Content_Types].xml`, `_rels/.rels`, `word/document.xml`. `[Content_Types].xml` must declare `/word/document.xml` with the plain Word main content type, which excludes macro-enabled (`.docm`) and template packages. `_rels/.rels` must contain an `officeDocument` relationship targeting `word/document.xml`. The three XML parts must be well formed with the expected root element. XML is parsed incrementally with the standard library after a scan that rejects any `<!DOCTYPE` or `<!ENTITY`, so entities are never resolved.

The ZIP checks run on a bounded input (at most `max_file_bytes`), so worst-case CPU work is bounded by the limits above.

## 2. Source store (ING-005)

`LocalSourceDocumentStore(root, max_file_bytes=...)` implements `put`, `get`, and `delete` of the port. The methods are `async` and run blocking file work in a worker thread.

- `initialize()` is the only method that creates directories. It rejects a symlinked root, a root owned by another user, and a root writable by group or others, then pins the root as a directory file descriptor. All later operations are relative to that descriptor.
- A key has the shape `<2 hex>/<32 hex>` (for example `3f/9c1d...`), generated from `secrets.token_hex`. It carries no user input and satisfies the domain `StorageKey` rules. The structure is not a public contract.
- `get` and `delete` first match the key against that exact shape. Anything else, including `..`, absolute paths, and backslashes, raises `ING_NOT_FOUND` without touching the filesystem. Every path component is then opened with `O_NOFOLLOW`, so a symlink planted in the store is never followed. A symlink or non-regular file found there raises `ING_INTERNAL_ERROR`.
- `put` writes a `.tmp-*` file in the final directory (`O_CREAT|O_EXCL|O_NOFOLLOW`, mode `0600`), flushes and `fsync`s it, then publishes it with a hard link that fails if the name exists, unlinks the temp name, and `fsync`s the directory. A name collision draws a new key (up to 8 times) and never overwrites another blob. On any failure the temp file is removed and no key is returned. Readers cannot see a partial file because they only open final names.
- `put` rejects empty content (`ING_INVALID_DOCUMENT`) and content above the limit (`ING_FILE_TOO_LARGE`). `get` rejects a stored file above the limit (`ING_INTERNAL_ERROR`).
- `delete` is idempotent. A missing blob is success.
- Errors never carry paths or OS messages.

Limitations:

- POSIX only (macOS, Linux). `initialize()` fails on platforms without directory-relative file operations.
- A process crash between temp creation and unlink can leave a `.tmp-*` file. It is invisible to `get`, but there is no sweeper yet. A later cleanup task may delete temp files that are older than a safe threshold.
- Durability depends on `fsync` honoring the storage stack. On macOS `fsync` does not force the drive cache to stable storage (`F_FULLFSYNC`). The adapter does not use `F_FULLFSYNC`.

## 3. Registry (ING-006)

### Lifecycle

`SqliteDatabase(path)` does nothing until `initialize()` (create directory `0700`, file `0600`, set WAL, apply migrations) or `connect()` (open an existing, current-version database, never create or migrate). `connect()` returns a `SqliteConnection`. Each repository takes one. A connection serializes its own use with a lock and runs every repository call in a single transaction (`BEGIN IMMEDIATE` for writes). Separate connections, in one process or several, rely on SQLite locking and a 5-second `busy_timeout`. Use one connection per worker or per request scope and call `close()`.

Every connection enables `PRAGMA foreign_keys` and verifies it. Timestamps are stored as fixed-width UTC text (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) so SQL comparison is chronological.

### Migrations

`MIGRATIONS` in `sqlite_database.py` is an append-only list. Version 1 creates `schema_migrations`, `documents`, `document_versions`, `index_generations`, `ingestion_jobs`, and `ingestion_job_attempts`. `initialize()` records each migration and sets `PRAGMA user_version` in the same transaction as the DDL. It fails fast with `ING_INTERNAL_ERROR`, before writing anything, on a newer `user_version`, a database with objects but no version, a failing `quick_check`, or a `schema_migrations` table that disagrees with `user_version`. There is no downgrade.

### Database-level protection

- Composite foreign keys tie versions to documents, generations to an existing `(document, version)`, the active pointer to a generation of the same document and version, and jobs to their document, version, and generation.
- `CHECK` constraints mirror the model invariants: pointer pairing, deleted documents without a pointer, job status and stage rules, `attempt` rules, error code presence, lease pairing, and `updated_at >= created_at`.
- A partial unique index allows at most one `active` generation per document.
- `idempotency_key` is globally unique, because the accepted contract defines no narrower scope.
- `storage_key` is unique, so one blob cannot be shared by two versions.

### Repository behavior beyond the signatures

These rules fill gaps that the contract leaves open. None of them changes a signature or an error code.

| Operation | Behavior |
| --- | --- |
| `DocumentRepository.create` | Rejects a record that already has a pointer or `deleted_at` (`ING_INVALID_STATE`). |
| `add_version` | The version must be the previous maximum plus one, otherwise `ING_CONFLICT`. A reused `storage_key` is `ING_CONFLICT`. A deleted document raises `ING_INVALID_STATE`. |
| `add_generation` | The generation must be `staged`. The document and version must exist. A deleted document raises `ING_INVALID_STATE`. |
| `set_generation_state` | Applies the domain transitions, with two restrictions that protect the pointer: `staged → active` is reserved for `publish_generation`, and `active → superseded` is refused while the generation is the active pointer. After `mark_deleted` cleared the pointer, `active → superseded` is allowed. |
| `publish_generation` | Compares the current pointer with `expected_active_generation_id` first (`ING_CONFLICT`), then requires a `staged` generation of a live document (`ING_INVALID_STATE`). It supersedes the predecessor, activates the new generation, and moves the pointer in one transaction. |
| `mark_deleted` | Idempotent. A second call keeps the first `deleted_at`. Generation rows keep their state. |
| `IngestionJobRepository.enqueue` | The job must be `queued` with `attempt = 0`. Referenced document, version, and generation must exist (`ING_NOT_FOUND`). Same key and fingerprint returns the stored job. Same key with another fingerprint is `ING_CONFLICT`. A duplicate `job_id` under a new key is `ING_CONFLICT`. |
| `claim` | Picks the oldest queued job (by `created_at`) that is not newer than `now` and whose document has no job in `processing` (ADR-ING-001: one publishing operation per document). Increments `attempt`, sets stage `validating`, owner, and lease, and writes an attempt row. |
| `heartbeat`, `record_stage`, `complete`, `fail` | Compare-and-swap on `attempt`. A different attempt is always `ING_CONFLICT`, checked before the status. A matching attempt on a job that is not `processing` is `ING_INVALID_STATE`. An expired but not yet released lease does not block the current attempt. Only a newer claim fences it. |
| `fail` | `error_code` must be a known `ING_*` code, otherwise `ING_INVALID_STATE`. |
| `requeue` | Only `failed → queued`. Keeps `attempt` and the attempt history, clears stage and error code. The next claim increments `attempt`. |
| `release_expired` | Moves `processing` jobs whose lease ended at or before `now` to `queued`, keeps `attempt`, and closes the attempt row as `released`. Each row is updated with a guard on status, attempt, and lease, so a job that was reclaimed in the meantime is skipped. |

`updated_at` never moves backwards. If a caller passes a `now` earlier than the stored `updated_at`, the stored value is kept.

`ingestion_job_attempts` keeps one row per claim (worker, lease, last stage, outcome `completed`, `failed`, or `released`, error code). Requeue and recovery never delete it. The domain `IngestionJob` still exposes only its current state.

## 4. Non-atomic boundaries

The source store and the registry share no transaction. The intended order is: validate, `put` (finalized), then registry writes. The registry never references a source that is not finalized.

- A failure after `put` and before the registry commit leaves an orphan blob. The registry is the authority: a blob is removable only if no `document_versions.storage_key` references it.
- The ports expose one transaction per method. Creating a document, adding its first version, and enqueueing its job are therefore three commits. A failure between them leaves a document or version without a job, never a dangling reference. The use case (ING-022) must make that sequence safe to repeat, using the idempotency key. A single multi-repository transaction would need a unit-of-work port, which is a contract change and was not introduced.
- `publish_generation` is a compare-and-set on the document pointer only. It receives no `attempt`, so the adapter cannot tell whether the caller still owns the job. ING-018/019 must close this before the worker publishes. The options are passing a fencing token through the port (a contract and ADR-ING-003 change) or verifying `claim` ownership in the use case right before publishing.
- Lease expiry timing, heartbeats, retry limits, and backoff belong to the worker (ING-019–020). The repository only provides the atomic primitives.
- The canonical request fingerprint is computed by the caller. The repository stores and compares the string (1 to 512 characters) and does not interpret it.
