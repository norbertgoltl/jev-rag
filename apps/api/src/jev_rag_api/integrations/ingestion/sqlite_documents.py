"""SQLite implementation of ``DocumentRepository`` (ING-006).

Each method is one write (or read) transaction. Cross-table invariants that SQLite cannot
express are checked inside that transaction, with foreign keys and constraints as a backstop.
"""

import sqlite3
from datetime import datetime
from uuid import UUID

from jev_rag_api.domain.ingestion.enums import IndexGenerationState
from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionInternalError,
    IngestionInvalidStateError,
    IngestionNotFoundError,
)
from jev_rag_api.domain.ingestion.models import DocumentRecord, DocumentVersion, IndexGeneration
from jev_rag_api.domain.ingestion.transitions import validate_generation_transition
from jev_rag_api.integrations.ingestion.sqlite_database import (
    SqliteConnection,
    from_db_time,
    to_db_time,
)


def _document_from_row(row: sqlite3.Row | tuple[object, ...]) -> DocumentRecord:
    document_id, created_at, active_version, active_generation_id, deleted_at = row
    return DocumentRecord.model_validate(
        {
            "document_id": document_id,
            "created_at": from_db_time(str(created_at)),
            "active_version": active_version,
            "active_index_generation_id": active_generation_id,
            "deleted_at": from_db_time(str(deleted_at)) if deleted_at is not None else None,
        }
    )


def _version_from_row(row: tuple[object, ...]) -> DocumentVersion:
    document_id, version, sha, source_name, media_type, storage_key, created_at = row
    return DocumentVersion.model_validate(
        {
            "document_id": document_id,
            "version": version,
            "content_sha256": sha,
            "source_name": source_name,
            "media_type": media_type,
            "storage_key": storage_key,
            "created_at": from_db_time(str(created_at)),
        }
    )


def _generation_from_row(row: tuple[object, ...]) -> IndexGeneration:
    generation_id, document_id, document_version, fingerprint, state, created_at = row
    return IndexGeneration.model_validate(
        {
            "generation_id": generation_id,
            "document_id": document_id,
            "document_version": document_version,
            "pipeline_fingerprint": fingerprint,
            "state": state,
            "created_at": from_db_time(str(created_at)),
        }
    )


_DOCUMENT_COLUMNS = "document_id, created_at, active_version, active_generation_id, deleted_at"
_VERSION_COLUMNS = (
    "document_id, version, content_sha256, source_name, media_type, storage_key, created_at"
)
_GENERATION_COLUMNS = (
    "generation_id, document_id, document_version, pipeline_fingerprint, state, created_at"
)


def _load_document(connection: sqlite3.Connection, document_id: UUID) -> DocumentRecord:
    row = connection.execute(
        f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE document_id = ?", (str(document_id),)
    ).fetchone()
    if row is None:
        raise IngestionNotFoundError()
    return _document_from_row(row)


def _load_generation(connection: sqlite3.Connection, generation_id: UUID) -> IndexGeneration:
    row = connection.execute(
        f"SELECT {_GENERATION_COLUMNS} FROM index_generations WHERE generation_id = ?",
        (str(generation_id),),
    ).fetchone()
    if row is None:
        raise IngestionNotFoundError()
    return _generation_from_row(row)


class SqliteDocumentRepository:
    def __init__(self, connection: SqliteConnection) -> None:
        self._connection = connection

    async def create(self, document: DocumentRecord) -> DocumentRecord:
        if document.active_version is not None or document.deleted_at is not None:
            # A new document cannot point at versions that do not exist yet.
            raise IngestionInvalidStateError()

        def work(connection: sqlite3.Connection) -> DocumentRecord:
            if connection.execute(
                "SELECT 1 FROM documents WHERE document_id = ?", (str(document.document_id),)
            ).fetchone():
                raise IngestionConflictError()
            connection.execute(
                "INSERT INTO documents (document_id, created_at) VALUES (?, ?)",
                (str(document.document_id), to_db_time(document.created_at)),
            )
            return _load_document(connection, document.document_id)

        return await self._connection.run(work)

    async def get(self, document_id: UUID) -> DocumentRecord:
        return await self._connection.run(
            lambda connection: _load_document(connection, document_id), write=False
        )

    async def add_version(self, version: DocumentVersion) -> DocumentVersion:
        def work(connection: sqlite3.Connection) -> DocumentVersion:
            document = _load_document(connection, version.document_id)
            if document.deleted_at is not None:
                raise IngestionInvalidStateError()
            latest = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM document_versions WHERE document_id = ?",
                (str(version.document_id),),
            ).fetchone()[0]
            if version.version != latest + 1:
                raise IngestionConflictError()
            if connection.execute(
                "SELECT 1 FROM document_versions WHERE storage_key = ?", (version.storage_key,)
            ).fetchone():
                raise IngestionConflictError()
            connection.execute(
                f"INSERT INTO document_versions ({_VERSION_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(version.document_id),
                    version.version,
                    version.content_sha256,
                    version.source_name,
                    version.media_type,
                    version.storage_key,
                    to_db_time(version.created_at),
                ),
            )
            return _load_version(connection, version.document_id, version.version)

        return await self._connection.run(work)

    async def get_version(self, document_id: UUID, version: int) -> DocumentVersion:
        return await self._connection.run(
            lambda connection: _load_version(connection, document_id, version), write=False
        )

    async def add_generation(self, generation: IndexGeneration) -> IndexGeneration:
        if generation.state is not IndexGenerationState.STAGED:
            raise IngestionInvalidStateError()

        def work(connection: sqlite3.Connection) -> IndexGeneration:
            document = _load_document(connection, generation.document_id)
            _load_version(connection, generation.document_id, generation.document_version)
            if document.deleted_at is not None:
                raise IngestionInvalidStateError()
            if connection.execute(
                "SELECT 1 FROM index_generations WHERE generation_id = ?",
                (str(generation.generation_id),),
            ).fetchone():
                raise IngestionConflictError()
            connection.execute(
                f"INSERT INTO index_generations ({_GENERATION_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(generation.generation_id),
                    str(generation.document_id),
                    generation.document_version,
                    generation.pipeline_fingerprint,
                    generation.state.value,
                    to_db_time(generation.created_at),
                ),
            )
            return _load_generation(connection, generation.generation_id)

        return await self._connection.run(work)

    async def set_generation_state(
        self, generation_id: UUID, state: IndexGenerationState
    ) -> IndexGeneration:
        """Apply an allowed transition.

        ``staged -> active`` is reserved for ``publish_generation``. ``active -> superseded``
        is refused while the generation is still the document's active pointer, so the pointer
        and the state can never disagree.
        """

        def work(connection: sqlite3.Connection) -> IndexGeneration:
            generation = _load_generation(connection, generation_id)
            validate_generation_transition(generation.state, state)
            if state is IndexGenerationState.ACTIVE:
                raise IngestionInvalidStateError()
            if (
                state is IndexGenerationState.SUPERSEDED
                and connection.execute(
                    "SELECT 1 FROM documents WHERE document_id = ? AND active_generation_id = ?",
                    (str(generation.document_id), str(generation_id)),
                ).fetchone()
            ):
                raise IngestionInvalidStateError()
            cursor = connection.execute(
                "UPDATE index_generations SET state = ? WHERE generation_id = ? AND state = ?",
                (state.value, str(generation_id), generation.state.value),
            )
            if cursor.rowcount != 1:
                raise IngestionConflictError()
            return _load_generation(connection, generation_id)

        return await self._connection.run(work)

    async def get_active(self, document_id: UUID) -> IndexGeneration | None:
        def work(connection: sqlite3.Connection) -> IndexGeneration | None:
            document = _load_document(connection, document_id)
            if document.active_index_generation_id is None:
                return None
            return _load_generation(connection, document.active_index_generation_id)

        return await self._connection.run(work, write=False)

    async def publish_generation(
        self, generation_id: UUID, *, expected_active_generation_id: UUID | None
    ) -> DocumentRecord:
        def work(connection: sqlite3.Connection) -> DocumentRecord:
            generation = _load_generation(connection, generation_id)
            document = _load_document(connection, generation.document_id)
            if document.active_index_generation_id != expected_active_generation_id:
                raise IngestionConflictError()
            if (
                document.deleted_at is not None
                or generation.state is not IndexGenerationState.STAGED
            ):
                raise IngestionInvalidStateError()
            if document.active_index_generation_id is not None:
                superseded = connection.execute(
                    "UPDATE index_generations SET state = 'superseded' "
                    "WHERE generation_id = ? AND state = 'active'",
                    (str(document.active_index_generation_id),),
                )
                if superseded.rowcount != 1:
                    raise IngestionInternalError()
            activated = connection.execute(
                "UPDATE index_generations SET state = 'active' "
                "WHERE generation_id = ? AND state = 'staged'",
                (str(generation_id),),
            )
            pointer = connection.execute(
                "UPDATE documents SET active_version = ?, active_generation_id = ? "
                "WHERE document_id = ? AND active_generation_id IS ? AND deleted_at IS NULL",
                (
                    generation.document_version,
                    str(generation_id),
                    str(generation.document_id),
                    (
                        str(expected_active_generation_id)
                        if expected_active_generation_id is not None
                        else None
                    ),
                ),
            )
            if activated.rowcount != 1 or pointer.rowcount != 1:
                raise IngestionConflictError()
            return _load_document(connection, generation.document_id)

        return await self._connection.run(work)

    async def mark_deleted(self, document_id: UUID, *, deleted_at: datetime) -> DocumentRecord:
        def work(connection: sqlite3.Connection) -> DocumentRecord:
            document = _load_document(connection, document_id)
            if document.deleted_at is not None:
                return document
            connection.execute(
                "UPDATE documents SET deleted_at = ?, active_version = NULL, "
                "active_generation_id = NULL WHERE document_id = ? AND deleted_at IS NULL",
                (to_db_time(deleted_at), str(document_id)),
            )
            return _load_document(connection, document_id)

        return await self._connection.run(work)


def _load_version(
    connection: sqlite3.Connection, document_id: UUID, version: int
) -> DocumentVersion:
    row = connection.execute(
        f"SELECT {_VERSION_COLUMNS} FROM document_versions WHERE document_id = ? AND version = ?",
        (str(document_id), version),
    ).fetchone()
    if row is None:
        raise IngestionNotFoundError()
    return _version_from_row(row)
