# Document intake and persistence

Status: implemented by PR-ING-003 (ING-004). Source storage and the registry follow in PR-ING-004. Contracts are unchanged: see [contracts](contracts.md). Decisions: [ADR-ING-001](adr/ADR-ING-001-persistence-and-worker.md), [ADR-ING-002](adr/ADR-ING-002-identities-and-idempotency.md), [ADR-ING-003](adr/ADR-ING-003-index-publication.md).

Adapters live in `apps/api/src/jev_rag_api/integrations/ingestion/`. None of them runs at import time or when `Settings` is created.

| Module | Task | Responsibility |
| --- | --- | --- |
| `content_validation.py` | ING-004 | Bounded, content-based validation of source bytes |

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
