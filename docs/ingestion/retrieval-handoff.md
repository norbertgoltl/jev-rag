# Retrieval handoff

Status: contract version 1 for ING-001 and ING-002. Consumer: 03 Retrieval. Related: [architecture](architecture.md), [contracts](contracts.md), [ADR-ING-003](adr/ADR-ING-003-index-publication.md).

Changing the payload or the rules below requires a new `schema_version`, a migration plan, and a reindexing plan.

## 1. Point and payload

The Qdrant point ID is the deterministic `chunk_id` UUIDv5 (see [contracts §2](contracts.md#2-identifiers-and-formats)). The raw full document is never stored in Qdrant. The chunk `text` is stored in the payload so a search result is displayable.

Payload schema version `1`:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | int, `1` | Required on every point. |
| `document_id` | UUID string | Logical document. |
| `document_version` | int ≥ 1 | Source version. |
| `index_generation_id` | UUID string | Generation that produced the point. |
| `chunk_id` | UUID string | Equal to the point ID. |
| `chunk_index` | int ≥ 0 | Position in the generation. |
| `text` | string | Chunk text. |
| `language` | `hu`, `en`, `mixed`, `unknown` | Detected language. |
| `source_name` | string | Original base file name. |
| `page_start`, `page_end` | int ≥ 1 or null | Page range. Null when the parser has no reliable page. Never an invented value. |
| `section_path` | list of strings | Heading path. Possibly empty. |
| `embedding_model_id` | string | Model that produced the vector. |
| `visibility` | `staged`, `active`, `inactive` | Search optimization and transient-state marker. |

All values are JSON compatible and round-trip through JSON unchanged.

## 2. Active generation rule

1. The registry is the authority on the active document version and index generation. `DocumentRepository.get_active(document_id)` returns it.
2. Retrieval must not treat `visibility = active` in Qdrant as the sole truth.
3. A search result is acceptable only if its `index_generation_id` equals the registry's active generation for its `document_id`. Results from other generations are dropped.
4. A deleted document (`deleted_at` set, no active generation) yields no results, even while Qdrant cleanup is pending.

Reason: switching the active pointer and updating Qdrant payloads are not atomic. Between the two steps an old generation may still be marked `active`, or a new one still `staged`. Without the registry check, Retrieval could return an old chunk.

Retrieval may use `visibility = active` as a search-time filter to reduce candidates. It must then still apply the registry check to every returned hit.

## 3. Collection compatibility

A collection is compatible when all of these match:

- embedding model identifier,
- vector dimension,
- distance metric,
- payload schema version.

On a mismatch the writer raises `ING_INDEX_INCOMPATIBLE` and does not continue with silent conversion. A different model needs a new collection or a full reindex.

## 4. Query embedding

A query embedding must come from a compatible model family and configuration: the same model identifier, dimension, and metric as the indexed documents. Model-dependent `query` and `document` prefixes or instructions belong to the embedding provider contract (`embed_query`, `embed_documents`). Retrieval does not hard-code them.

## 5. Open items for Retrieval

| Item | Note |
| --- | --- |
| Payload indexes | Chosen from real filter patterns in ING-016–017. |
| Score semantics | Depend on the metric of the selected model. |
| Access scope filter | Future. Does not replace application-side authorization. |
