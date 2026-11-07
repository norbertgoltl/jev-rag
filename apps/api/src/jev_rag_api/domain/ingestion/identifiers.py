import hashlib
import re
from uuid import UUID, uuid5

INGESTION_NAMESPACE = UUID("821ab20b-0823-42ac-b401-92927700a19e")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_sha256(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def derive_chunk_id(
    *,
    document_id: UUID,
    document_version: int,
    index_generation_id: UUID,
    chunk_index: int,
    content_sha256: str,
) -> UUID:
    """Derive the deterministic chunk and Qdrant point ID.

    The canonical tuple is documented in docs/ingestion/contracts.md. Changing the
    namespace or the tuple layout is a breaking identifier migration.
    """
    canonical = (
        f"{document_id}:{document_version}:{index_generation_id}:{chunk_index}:{content_sha256}"
    )
    return uuid5(INGESTION_NAMESPACE, canonical)
