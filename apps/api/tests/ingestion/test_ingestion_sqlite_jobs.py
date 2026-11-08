import asyncio
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from async_support import async_test
from registry_support import (
    FINGERPRINT,
    T0,
    Registry,
    at,
    make_database,
    make_generation,
    make_queued_job,
    make_version,
    raw_db,
)

from jev_rag_api.domain.ingestion.enums import JobStage, JobStatus, JobType
from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionInvalidStateError,
    IngestionNotFoundError,
)
from jev_rag_api.integrations.ingestion.sqlite_database import SqliteDatabase

LEASE = 60


@pytest.fixture
def database(tmp_path: Path) -> SqliteDatabase:
    return make_database(tmp_path)


@pytest.fixture
def registry(database: SqliteDatabase) -> Iterator[Registry]:
    instance = Registry(database)
    yield instance
    instance.close()


def raw_rows(database_path: Path, sql: str) -> list[tuple[object, ...]]:
    with raw_db(database_path) as connection:
        return connection.execute(sql).fetchall()


@async_test
async def test_job_01_enqueue_persists_key_and_fingerprint_with_the_job(
    registry: Registry, tmp_path: Path
) -> None:
    job = await registry.seed_job("upload-1")
    assert job.status is JobStatus.QUEUED and job.attempt == 0
    rows = raw_rows(
        tmp_path / "data" / "registry.sqlite3",
        "SELECT job_id, idempotency_key, request_fingerprint FROM ingestion_jobs",
    )
    assert rows == [(str(job.job_id), "upload-1", FINGERPRINT)]
    assert await registry.jobs.get(job.job_id) == job
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.get(uuid4())


@async_test
async def test_job_02_same_key_and_fingerprint_returns_original_after_restart(
    database: SqliteDatabase, registry: Registry
) -> None:
    original = await registry.seed_job("key-1")
    registry.close()
    reopened = Registry(database)
    try:
        duplicate = make_queued_job(original.document_id, created_at=at(500))
        again = await reopened.jobs.enqueue(
            duplicate, idempotency_key="key-1", request_fingerprint=FINGERPRINT
        )
        assert again == original
        assert again.job_id != duplicate.job_id
        count = reopened.connection.run_sync(
            lambda c: c.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0], write=False
        )
        assert count == 1
    finally:
        reopened.close()


@async_test
async def test_job_03_same_key_with_other_fingerprint_conflicts_and_changes_nothing(
    registry: Registry,
) -> None:
    original = await registry.seed_job("key-1")
    with pytest.raises(IngestionConflictError):
        await registry.jobs.enqueue(
            make_queued_job(original.document_id),
            idempotency_key="key-1",
            request_fingerprint="d" * 64,
        )
    assert await registry.jobs.get(original.job_id) == original
    assert (
        registry.connection.run_sync(
            lambda c: c.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0], write=False
        )
        == 1
    )


@async_test
async def test_enqueue_validates_arguments_references_and_state(registry: Registry) -> None:
    document_id = await registry.seed_document()
    for key, fingerprint in (("", FINGERPRINT), ("k", ""), ("k" * 513, FINGERPRINT), (" ", "f")):
        with pytest.raises(ValueError, match="1-512"):
            await registry.jobs.enqueue(
                make_queued_job(document_id), idempotency_key=key, request_fingerprint=fingerprint
            )
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.enqueue(
            make_queued_job(uuid4()), idempotency_key="a", request_fingerprint=FINGERPRINT
        )
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.enqueue(
            make_queued_job(document_id, version=7), idempotency_key="b", request_fingerprint="f"
        )
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.enqueue(
            make_queued_job(document_id, generation_id=uuid4()),
            idempotency_key="c",
            request_fingerprint="f",
        )
    started = make_queued_job(document_id).model_copy(update={"attempt": 1})
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.enqueue(started, idempotency_key="d", request_fingerprint="f")
    same_id = make_queued_job(document_id)
    await registry.jobs.enqueue(same_id, idempotency_key="e", request_fingerprint="f")
    with pytest.raises(IngestionConflictError):
        await registry.jobs.enqueue(same_id, idempotency_key="other", request_fingerprint="f")


@async_test
async def test_enqueue_rejects_a_generation_of_another_document(registry: Registry) -> None:
    owner = await registry.seed_document()
    other = await registry.seed_document()
    generation = await registry.documents.add_generation(make_generation(owner))
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.enqueue(
            make_queued_job(other, generation_id=generation.generation_id),
            idempotency_key="x",
            request_fingerprint="f",
        )
    accepted = await registry.jobs.enqueue(
        make_queued_job(owner, generation_id=generation.generation_id, job_type=JobType.REINDEX),
        idempotency_key="y",
        request_fingerprint="f",
    )
    assert accepted.index_generation_id == generation.generation_id


@async_test
async def test_delete_job_may_omit_the_version(registry: Registry) -> None:
    document_id = await registry.seed_document()
    job = make_queued_job(document_id, version=None, job_type=JobType.DELETE)
    stored = await registry.jobs.enqueue(job, idempotency_key="del", request_fingerprint="f")
    assert stored.document_version is None


@async_test
async def test_job_04_concurrent_enqueue_with_one_key_creates_one_job(
    database: SqliteDatabase,
) -> None:
    setup = Registry(database)
    document_id = await setup.seed_document()
    setup.close()
    registries = [Registry(database) for _ in range(8)]
    try:
        results = await asyncio.gather(
            *(
                item.jobs.enqueue(
                    make_queued_job(document_id),
                    idempotency_key="shared",
                    request_fingerprint=FINGERPRINT,
                )
                for item in registries
            )
        )
        assert len({job.job_id for job in results}) == 1
        assert (
            registries[0].connection.run_sync(
                lambda c: c.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0],
                write=False,
            )
            == 1
        )
        mixed = await asyncio.gather(
            *(
                item.jobs.enqueue(
                    make_queued_job(document_id),
                    idempotency_key="race",
                    request_fingerprint=f"{index % 2}",
                )
                for index, item in enumerate(registries)
            ),
            return_exceptions=True,
        )
        winners = [r for r in mixed if not isinstance(r, BaseException)]
        losers = [r for r in mixed if isinstance(r, IngestionConflictError)]
        assert len(winners) + len(losers) == len(registries)
        assert len({job.job_id for job in winners}) == 1 and losers
    finally:
        for item in registries:
            item.close()


@async_test
async def test_claim_opens_attempt_one_with_lease_and_orders_by_age(registry: Registry) -> None:
    older = await registry.seed_job("a", created_at=at(0))
    newer = await registry.seed_job("b", created_at=at(5))
    assert await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(-1)) is None
    claimed = await registry.jobs.claim(worker_id="w1", lease_seconds=LEASE, now=at(10))
    assert claimed is not None
    assert claimed.job_id == older.job_id
    assert (claimed.status, claimed.stage, claimed.attempt) == (
        JobStatus.PROCESSING,
        JobStage.VALIDATING,
        1,
    )
    second = await registry.jobs.claim(worker_id="w2", lease_seconds=LEASE, now=at(10))
    assert second is not None and second.job_id == newer.job_id
    assert await registry.jobs.claim(worker_id="w3", lease_seconds=LEASE, now=at(10)) is None


@async_test
async def test_claim_validates_arguments(registry: Registry) -> None:
    with pytest.raises(ValueError, match="worker"):
        await registry.jobs.claim(worker_id=" ", lease_seconds=LEASE, now=T0)
    with pytest.raises(ValueError, match="worker"):
        await registry.jobs.claim(worker_id="w", lease_seconds=0, now=T0)
    with pytest.raises(ValueError, match="timezone"):
        await registry.jobs.claim(worker_id="w", lease_seconds=1, now=T0.replace(tzinfo=None))


@async_test
async def test_claim_serializes_jobs_of_one_document(registry: Registry) -> None:
    document_id = await registry.seed_document()
    first = await registry.jobs.enqueue(
        make_queued_job(document_id, created_at=at(0)),
        idempotency_key="1",
        request_fingerprint="f",
    )
    await registry.jobs.enqueue(
        make_queued_job(document_id, created_at=at(1)),
        idempotency_key="2",
        request_fingerprint="f",
    )
    claimed = await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(5))
    assert claimed is not None and claimed.job_id == first.job_id
    assert await registry.jobs.claim(worker_id="w2", lease_seconds=LEASE, now=at(6)) is None
    await registry.jobs.complete(first.job_id, attempt=1, now=at(7))
    assert await registry.jobs.claim(worker_id="w2", lease_seconds=LEASE, now=at(8)) is not None


@async_test
async def test_job_05_concurrent_claims_from_separate_connections_never_share_a_job(
    database: SqliteDatabase,
) -> None:
    setup = Registry(database)
    await setup.seed_job("only")
    setup.close()
    registries = [Registry(database) for _ in range(8)]
    try:
        results = await asyncio.gather(
            *(
                item.jobs.claim(worker_id=f"w{index}", lease_seconds=LEASE, now=at(10))
                for index, item in enumerate(registries)
            )
        )
        claims = [job for job in results if job is not None]
        assert len(claims) == 1 and claims[0].attempt == 1
        attempts = registries[0].connection.run_sync(
            lambda c: c.execute(
                "SELECT job_id, attempt, worker_id FROM ingestion_job_attempts"
            ).fetchall(),
            write=False,
        )
        assert len(attempts) == 1
    finally:
        for item in registries:
            item.close()


@async_test
async def test_job_05_many_jobs_are_each_claimed_once_by_competing_workers(
    database: SqliteDatabase,
) -> None:
    setup = Registry(database)
    for index in range(6):
        await setup.seed_job(f"k{index}", created_at=at(index))
    setup.close()
    registries = [Registry(database) for _ in range(4)]
    try:
        claimed: list[UUID] = []

        async def worker(item: Registry, name: str) -> None:
            while job := await item.jobs.claim(worker_id=name, lease_seconds=LEASE, now=at(100)):
                claimed.append(job.job_id)

        await asyncio.gather(*(worker(item, f"w{i}") for i, item in enumerate(registries)))
        assert len(claimed) == 6 and len(set(claimed)) == 6
    finally:
        for item in registries:
            item.close()


@async_test
async def test_heartbeat_extends_the_lease_for_the_current_attempt(
    registry: Registry, tmp_path: Path
) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(0))
    await registry.jobs.heartbeat(job.job_id, attempt=1, lease_seconds=LEASE, now=at(30))
    path = tmp_path / "data" / "registry.sqlite3"
    expires = raw_rows(path, "SELECT lease_expires_at FROM ingestion_jobs")[0][0]
    assert expires == "2026-03-01T12:01:30.000000Z"
    assert (
        registry.connection.run_sync(
            lambda c: c.execute("SELECT lease_expires_at FROM ingestion_job_attempts").fetchone()[
                0
            ],
            write=False,
        )
        == expires
    )
    assert await registry.jobs.release_expired(now=at(70)) == ()
    assert await registry.jobs.release_expired(now=at(90)) == (job.job_id,)


@async_test
async def test_job_06_stale_attempt_heartbeat_is_a_conflict(registry: Registry) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="old", lease_seconds=LEASE, now=at(0))
    await registry.jobs.release_expired(now=at(LEASE))
    reclaimed = await registry.jobs.claim(worker_id="new", lease_seconds=LEASE, now=at(LEASE + 1))
    assert reclaimed is not None and reclaimed.attempt == 2
    with pytest.raises(IngestionConflictError):
        await registry.jobs.heartbeat(job.job_id, attempt=1, lease_seconds=LEASE, now=at(70))
    await registry.jobs.heartbeat(job.job_id, attempt=2, lease_seconds=LEASE, now=at(70))
    with pytest.raises(IngestionConflictError):
        await registry.jobs.heartbeat(job.job_id, attempt=3, lease_seconds=LEASE, now=at(70))
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.heartbeat(uuid4(), attempt=1, lease_seconds=LEASE, now=at(70))
    with pytest.raises(ValueError, match="lease"):
        await registry.jobs.heartbeat(job.job_id, attempt=2, lease_seconds=0, now=at(70))


@async_test
async def test_job_07_stale_attempt_stage_complete_fail_conflict_and_job_stays_intact(
    registry: Registry,
) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="old", lease_seconds=LEASE, now=at(0))
    await registry.jobs.release_expired(now=at(LEASE))
    await registry.jobs.claim(worker_id="new", lease_seconds=LEASE, now=at(LEASE + 1))
    await registry.jobs.record_stage(
        job.job_id, attempt=2, stage=JobStage.EXTRACTING, now=at(LEASE + 2)
    )
    before = await registry.jobs.get(job.job_id)

    with pytest.raises(IngestionConflictError):
        await registry.jobs.record_stage(
            job.job_id, attempt=1, stage=JobStage.CHUNKING, now=at(LEASE + 3)
        )
    with pytest.raises(IngestionConflictError):
        await registry.jobs.complete(job.job_id, attempt=1, now=at(LEASE + 3))
    with pytest.raises(IngestionConflictError):
        await registry.jobs.fail(
            job.job_id, attempt=1, error_code="ING_INTERNAL_ERROR", now=at(LEASE + 3)
        )
    assert await registry.jobs.get(job.job_id) == before
    assert before.stage is JobStage.EXTRACTING and before.attempt == 2


@async_test
async def test_stale_attempt_after_terminal_state_is_still_a_conflict(registry: Registry) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(0))
    await registry.jobs.complete(job.job_id, attempt=1, now=at(1))
    with pytest.raises(IngestionConflictError):
        await registry.jobs.complete(job.job_id, attempt=0, now=at(2))
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.complete(job.job_id, attempt=1, now=at(2))
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.INDEXING, now=at(2))


@async_test
async def test_complete_and_fail_terminal_transitions(registry: Registry) -> None:
    done = await registry.seed_job("done")
    broken = await registry.seed_job("broken")
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(0))
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(0))
    await registry.jobs.record_stage(done.job_id, attempt=1, stage=JobStage.FINALIZING, now=at(1))
    completed = await registry.jobs.complete(done.job_id, attempt=1, now=at(2))
    assert (completed.status, completed.stage, completed.error_code) == (
        JobStatus.COMPLETED,
        None,
        None,
    )
    await registry.jobs.record_stage(broken.job_id, attempt=1, stage=JobStage.EMBEDDING, now=at(1))
    failed = await registry.jobs.fail(
        broken.job_id, attempt=1, error_code="ING_EMBEDDING_UNAVAILABLE", now=at(3)
    )
    assert (failed.status, failed.stage, failed.error_code) == (
        JobStatus.FAILED,
        JobStage.EMBEDDING,
        "ING_EMBEDDING_UNAVAILABLE",
    )
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.fail(done.job_id, attempt=1, error_code="NOT_A_CODE", now=at(4))
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.fail(
            broken.job_id, attempt=1, error_code="ING_INTERNAL_ERROR", now=at(4)
        )


@async_test
async def test_requeue_is_only_for_failed_jobs_and_keeps_history(
    registry: Registry, tmp_path: Path
) -> None:
    job = await registry.seed_job()
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.requeue(job.job_id, now=at(1))
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(0))
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.requeue(job.job_id, now=at(1))
    await registry.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.CHUNKING, now=at(1))
    await registry.jobs.fail(job.job_id, attempt=1, error_code="ING_INVALID_CHUNK", now=at(2))

    queued = await registry.jobs.requeue(job.job_id, now=at(3))
    assert (queued.status, queued.stage, queued.error_code, queued.attempt) == (
        JobStatus.QUEUED,
        None,
        None,
        1,
    )
    reclaimed = await registry.jobs.claim(worker_id="w2", lease_seconds=LEASE, now=at(4))
    assert reclaimed is not None and reclaimed.attempt == 2
    history = raw_rows(
        tmp_path / "data" / "registry.sqlite3",
        "SELECT attempt, worker_id, outcome, error_code, last_stage "
        "FROM ingestion_job_attempts ORDER BY attempt",
    )
    assert history == [
        (1, "w", "failed", "ING_INVALID_CHUNK", "chunking"),
        (2, "w2", None, None, "validating"),
    ]
    with pytest.raises(IngestionNotFoundError):
        await registry.jobs.requeue(uuid4(), now=at(5))


@async_test
async def test_job_08_release_expired_returns_only_expired_jobs_and_invalidates_token(
    registry: Registry,
) -> None:
    expiring = await registry.seed_job("a")
    healthy = await registry.seed_job("b")
    await registry.jobs.claim(worker_id="w1", lease_seconds=10, now=at(0))
    await registry.jobs.claim(worker_id="w2", lease_seconds=1000, now=at(0))
    released = await registry.jobs.release_expired(now=at(10))
    assert released == (expiring.job_id,)
    after = await registry.jobs.get(expiring.job_id)
    assert (after.status, after.stage, after.attempt) == (JobStatus.QUEUED, None, 1)
    assert (await registry.jobs.get(healthy.job_id)).status is JobStatus.PROCESSING
    assert await registry.jobs.release_expired(now=at(10)) == ()
    with pytest.raises(IngestionInvalidStateError):
        await registry.jobs.heartbeat(expiring.job_id, attempt=1, lease_seconds=5, now=at(11))
    again = await registry.jobs.claim(worker_id="w3", lease_seconds=LEASE, now=at(11))
    assert again is not None and again.job_id == expiring.job_id and again.attempt == 2
    with pytest.raises(IngestionConflictError):
        await registry.jobs.complete(expiring.job_id, attempt=1, now=at(12))


@async_test
async def test_release_expired_keeps_attempt_history(registry: Registry, tmp_path: Path) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="w", lease_seconds=5, now=at(0))
    await registry.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.EMBEDDING, now=at(1))
    await registry.jobs.release_expired(now=at(5))
    rows = raw_rows(
        tmp_path / "data" / "registry.sqlite3",
        "SELECT attempt, outcome, last_stage FROM ingestion_job_attempts",
    )
    assert rows == [(1, "released", "embedding")]


@async_test
async def test_job_10_a_late_release_cannot_overwrite_a_newer_claim(
    database: SqliteDatabase,
) -> None:
    first = Registry(database)
    second = Registry(database)
    try:
        job = await first.seed_job()
        await first.jobs.claim(worker_id="w1", lease_seconds=5, now=at(0))
        # Worker 2's recovery runs first, then a new claim extends the lease far into the future.
        assert await second.jobs.release_expired(now=at(6)) == (job.job_id,)
        claimed = await second.jobs.claim(worker_id="w2", lease_seconds=1000, now=at(7))
        assert claimed is not None and claimed.attempt == 2
        # A recovery pass that looks at the same instant must not touch the fresh claim.
        assert await first.jobs.release_expired(now=at(8)) == ()
        current = await first.jobs.get(job.job_id)
        assert (current.status, current.attempt) == (JobStatus.PROCESSING, 2)
        with pytest.raises(IngestionConflictError):
            await first.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.INDEXING, now=at(9))
    finally:
        first.close()
        second.close()


@async_test
async def test_updated_at_never_moves_backwards(registry: Registry) -> None:
    job = await registry.seed_job()
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(100))
    await registry.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.CHUNKING, now=at(50))
    assert (await registry.jobs.get(job.job_id)).updated_at == at(100)
    done = await registry.jobs.complete(job.job_id, attempt=1, now=at(60))
    assert done.updated_at == at(100)


@async_test
async def test_job_state_survives_reopening(database: SqliteDatabase, registry: Registry) -> None:
    job = await registry.seed_job("persist")
    await registry.jobs.claim(worker_id="w", lease_seconds=LEASE, now=at(1))
    await registry.jobs.record_stage(job.job_id, attempt=1, stage=JobStage.NORMALIZING, now=at(2))
    registry.close()
    reopened = Registry(database)
    try:
        stored = await reopened.jobs.get(job.job_id)
        assert (stored.status, stored.stage, stored.attempt) == (
            JobStatus.PROCESSING,
            JobStage.NORMALIZING,
            1,
        )
        assert stored.created_at == job.created_at and stored.updated_at == at(2)
    finally:
        reopened.close()


@async_test
async def test_int_03_constraint_violation_rolls_back_partial_rows(
    database: SqliteDatabase, registry: Registry
) -> None:
    document_id = await registry.seed_document()
    broken = make_queued_job(document_id)

    def violating(connection: sqlite3.Connection) -> None:
        connection.execute(
            "INSERT INTO documents (document_id, created_at) VALUES (?, ?)",
            (str(uuid4()), "2026-01-01T00:00:00.000000Z"),
        )
        connection.execute(
            "INSERT INTO ingestion_jobs (job_id, job_type, document_id, document_version, status, "
            "attempt, created_at, updated_at, idempotency_key, request_fingerprint) "
            "VALUES (?, 'ingest', ?, 1, 'processing', 0, 'a', 'a', 'k', 'f')",
            (str(broken.job_id), str(document_id)),
        )

    with pytest.raises(IngestionConflictError):
        await registry.connection.run(violating)
    counts = registry.connection.run_sync(
        lambda c: (
            c.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            c.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0],
        ),
        write=False,
    )
    assert counts == (1, 0)


@async_test
async def test_database_rejects_inconsistent_job_rows(registry: Registry, tmp_path: Path) -> None:
    job = await registry.seed_job()
    path = tmp_path / "data" / "registry.sqlite3"
    with raw_db(path) as raw:
        raw.execute("PRAGMA foreign_keys = ON")
        for sql in (
            "UPDATE ingestion_jobs SET status = 'processing', attempt = 1",  # no stage or lease
            "UPDATE ingestion_jobs SET attempt = -1",
            "UPDATE ingestion_jobs SET status = 'failed', attempt = 1",  # no error code
            "UPDATE ingestion_jobs SET lease_owner = 'w'",  # half a lease
            "UPDATE ingestion_jobs SET updated_at = '0000'",
            "UPDATE ingestion_jobs SET idempotency_key = ''",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(sql)
        assert raw.execute("SELECT status, attempt FROM ingestion_jobs").fetchall() == [
            ("queued", 0)
        ]
    assert job.job_id


@async_test
async def test_version_references_survive_job_lifecycle(registry: Registry) -> None:
    document_id = await registry.seed_document()
    await registry.documents.add_version(make_version(document_id, 2))
    job = await registry.jobs.enqueue(
        make_queued_job(document_id, version=2), idempotency_key="v2", request_fingerprint="f"
    )
    assert job.document_version == 2
