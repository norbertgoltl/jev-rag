import sqlite3
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from async_support import async_test
from registry_support import (
    SHA,
    T0,
    Registry,
    at,
    make_database,
    make_generation,
    make_record,
    make_version,
    raw_db,
)

from jev_rag_api.domain.ingestion.enums import IndexGenerationState
from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionInvalidStateError,
    IngestionNotFoundError,
)
from jev_rag_api.integrations.ingestion.sqlite_database import SqliteDatabase


@pytest.fixture
def database(tmp_path: Path) -> SqliteDatabase:
    return make_database(tmp_path)


@pytest.fixture
def registry(database: SqliteDatabase) -> Iterator[Registry]:
    instance = Registry(database)
    yield instance
    instance.close()


@async_test
async def test_create_get_round_trip_and_conflict(registry: Registry) -> None:
    record = make_record()
    created = await registry.documents.create(record)
    assert created == record
    assert await registry.documents.get(record.document_id) == record
    with pytest.raises(IngestionConflictError):
        await registry.documents.create(record)
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.get(uuid4())


@async_test
async def test_create_rejects_prefilled_pointer_or_deletion(registry: Registry) -> None:
    deleted = make_record().model_copy(update={"deleted_at": T0})
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.create(deleted)
    pointed = make_record().model_copy(
        update={"active_version": 1, "active_index_generation_id": uuid4()}
    )
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.create(pointed)


@async_test
async def test_sql_04_equal_content_hash_keeps_documents_separate(registry: Registry) -> None:
    first = await registry.documents.create(make_record())
    second = await registry.documents.create(make_record())
    one = await registry.documents.add_version(make_version(first.document_id, sha=SHA))
    two = await registry.documents.add_version(make_version(second.document_id, sha=SHA))
    assert one.content_sha256 == two.content_sha256
    assert one.document_id != two.document_id
    assert one.storage_key != two.storage_key


@async_test
async def test_sql_05_versions_are_consecutive_and_individually_readable(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document(versions=3)
    for number in (1, 2, 3):
        assert (await registry.documents.get_version(document_id, number)).version == number
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.get_version(document_id, 4)
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.get_version(uuid4(), 1)
    with pytest.raises(IngestionConflictError):
        await registry.documents.add_version(make_version(document_id, 3))
    with pytest.raises(IngestionConflictError):
        await registry.documents.add_version(make_version(document_id, 5))
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.add_version(make_version(uuid4(), 1))


@async_test
async def test_add_version_rejects_reused_storage_key_and_deleted_documents(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document()
    existing = await registry.documents.get_version(document_id, 1)
    with pytest.raises(IngestionConflictError):
        await registry.documents.add_version(
            make_version(document_id, 2, storage_key=existing.storage_key)
        )
    await registry.documents.mark_deleted(document_id, deleted_at=at(1))
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.add_version(make_version(document_id, 2))


@async_test
async def test_sql_06_generation_requires_matching_version_and_staged_state(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document()
    other_id = await registry.seed_document()
    generation = make_generation(document_id)
    assert await registry.documents.add_generation(generation) == generation
    with pytest.raises(IngestionConflictError):
        await registry.documents.add_generation(generation)
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.add_generation(make_generation(document_id, version=2))
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.add_generation(make_generation(uuid4()))
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.add_generation(
            make_generation(other_id, state=IndexGenerationState.ACTIVE)
        )


@async_test
async def test_sql_06_generation_state_transitions(registry: Registry) -> None:
    document_id = await registry.seed_document()
    staged = await registry.documents.add_generation(make_generation(document_id))
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.set_generation_state(uuid4(), IndexGenerationState.FAILED)
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.set_generation_state(
            staged.generation_id, IndexGenerationState.SUPERSEDED
        )
    with pytest.raises(IngestionInvalidStateError):
        # staged -> active is allowed by the domain but owned by publish_generation.
        await registry.documents.set_generation_state(
            staged.generation_id, IndexGenerationState.ACTIVE
        )
    failed = await registry.documents.set_generation_state(
        staged.generation_id, IndexGenerationState.FAILED
    )
    assert failed.state is IndexGenerationState.FAILED
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.set_generation_state(
            staged.generation_id, IndexGenerationState.STAGED
        )


@async_test
async def test_sql_07_publish_switches_pointer_and_supersedes_predecessor(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document(versions=2)
    assert await registry.documents.get_active(document_id) is None
    first = await registry.documents.add_generation(make_generation(document_id, 1))
    second = await registry.documents.add_generation(make_generation(document_id, 2))

    published = await registry.documents.publish_generation(
        first.generation_id, expected_active_generation_id=None
    )
    assert (published.active_version, published.active_index_generation_id) == (
        1,
        first.generation_id,
    )
    active = await registry.documents.get_active(document_id)
    assert active is not None and active.state is IndexGenerationState.ACTIVE

    republished = await registry.documents.publish_generation(
        second.generation_id, expected_active_generation_id=first.generation_id
    )
    assert (republished.active_version, republished.active_index_generation_id) == (
        2,
        second.generation_id,
    )
    active = await registry.documents.get_active(document_id)
    assert active is not None and active.generation_id == second.generation_id
    assert registry.connection.run_sync(
        lambda c: dict(c.execute("SELECT generation_id, state FROM index_generations")), write=False
    ) == {
        str(first.generation_id): "superseded",
        str(second.generation_id): "active",
    }


@async_test
async def test_sql_07_publish_cas_mismatch_and_invalid_states_change_nothing(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document()
    first = await registry.documents.add_generation(make_generation(document_id))
    second = await registry.documents.add_generation(make_generation(document_id))
    await registry.documents.publish_generation(
        first.generation_id, expected_active_generation_id=None
    )

    with pytest.raises(IngestionConflictError):
        await registry.documents.publish_generation(
            second.generation_id, expected_active_generation_id=None
        )
    with pytest.raises(IngestionConflictError):
        await registry.documents.publish_generation(
            second.generation_id, expected_active_generation_id=uuid4()
        )
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.publish_generation(
            first.generation_id, expected_active_generation_id=first.generation_id
        )
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.publish_generation(uuid4(), expected_active_generation_id=None)
    active = await registry.documents.get_active(document_id)
    assert active is not None and active.generation_id == first.generation_id
    still_staged = await registry.documents.set_generation_state(
        second.generation_id, IndexGenerationState.FAILED
    )
    assert still_staged.state is IndexGenerationState.FAILED


@async_test
async def test_active_generation_cannot_be_superseded_while_pointed_to(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document()
    generation = await registry.documents.add_generation(make_generation(document_id))
    await registry.documents.publish_generation(
        generation.generation_id, expected_active_generation_id=None
    )
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.set_generation_state(
            generation.generation_id, IndexGenerationState.SUPERSEDED
        )
    await registry.documents.mark_deleted(document_id, deleted_at=at(5))
    superseded = await registry.documents.set_generation_state(
        generation.generation_id, IndexGenerationState.SUPERSEDED
    )
    assert superseded.state is IndexGenerationState.SUPERSEDED


@async_test
async def test_sql_08_mark_deleted_clears_pointer_and_is_idempotent(registry: Registry) -> None:
    document_id = await registry.seed_document()
    generation = await registry.documents.add_generation(make_generation(document_id))
    await registry.documents.publish_generation(
        generation.generation_id, expected_active_generation_id=None
    )
    deleted = await registry.documents.mark_deleted(document_id, deleted_at=at(10))
    assert deleted.deleted_at == at(10)
    assert deleted.active_version is None and deleted.active_index_generation_id is None
    assert await registry.documents.get_active(document_id) is None
    again = await registry.documents.mark_deleted(document_id, deleted_at=at(99))
    assert again.deleted_at == at(10)
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.mark_deleted(uuid4(), deleted_at=at(1))
    with pytest.raises(IngestionNotFoundError):
        await registry.documents.get_active(uuid4())
    # The version and its source reference survive: physical cleanup is a separate step.
    assert (await registry.documents.get_version(document_id, 1)).version == 1


@async_test
async def test_deleted_documents_accept_neither_generations_nor_publication(
    registry: Registry,
) -> None:
    document_id = await registry.seed_document()
    staged = await registry.documents.add_generation(make_generation(document_id))
    await registry.documents.mark_deleted(document_id, deleted_at=at(1))
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.add_generation(make_generation(document_id))
    with pytest.raises(IngestionInvalidStateError):
        await registry.documents.publish_generation(
            staged.generation_id, expected_active_generation_id=None
        )


@async_test
async def test_sql_03_state_survives_reopening_with_another_connection(
    database: SqliteDatabase, registry: Registry
) -> None:
    document_id = await registry.seed_document(versions=2)
    generation = await registry.documents.add_generation(make_generation(document_id, 2))
    await registry.documents.publish_generation(
        generation.generation_id, expected_active_generation_id=None
    )
    registry.close()

    reopened = Registry(database)
    try:
        record = await reopened.documents.get(document_id)
        assert record.active_version == 2
        assert record.active_index_generation_id == generation.generation_id
        assert (await reopened.documents.get_version(document_id, 2)).content_sha256 == SHA
        active = await reopened.documents.get_active(document_id)
        assert active == generation.model_copy(update={"state": IndexGenerationState.ACTIVE})
    finally:
        reopened.close()


@async_test
async def test_closed_connection_raises_a_domain_error(registry: Registry) -> None:
    from jev_rag_api.domain.ingestion.errors import IngestionInternalError

    registry.close()
    with pytest.raises(IngestionInternalError):
        await registry.documents.get(uuid4())


@async_test
async def test_database_constraints_backstop_the_adapter(
    database: SqliteDatabase, registry: Registry, tmp_path: Path
) -> None:
    document_id = await registry.seed_document()
    other_id = await registry.seed_document()
    generation = await registry.documents.add_generation(make_generation(document_id))
    path = tmp_path / "data" / "registry.sqlite3"
    with raw_db(path) as raw:
        raw.execute("PRAGMA foreign_keys = ON")
        # A pointer to a generation of another document violates the composite foreign key.
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "UPDATE documents SET active_version = 1, active_generation_id = ? "
                "WHERE document_id = ?",
                (str(generation.generation_id), str(other_id)),
            )
        # Half a pointer violates the check constraint.
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "UPDATE documents SET active_version = 1 WHERE document_id = ?", (str(document_id),)
            )
        # A generation for a version that does not exist is refused.
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "INSERT INTO index_generations VALUES (?, ?, 9, ?, 'staged', 'x')",
                (str(uuid4()), str(document_id), "c" * 64),
            )
        # Two active generations for one document violate the partial unique index.
        raw.execute(
            "UPDATE index_generations SET state = 'active' WHERE generation_id = ?",
            (str(generation.generation_id),),
        )
        second = make_generation(document_id)
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(
                "INSERT INTO index_generations VALUES (?, ?, 1, ?, 'active', 'x')",
                (str(second.generation_id), str(document_id), "c" * 64),
            )
