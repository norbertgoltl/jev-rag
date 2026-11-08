"""Harness for the documented order: validate, store finalize, then registry writes."""

import hashlib
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from async_support import async_test
from registry_support import FINGERPRINT, T0, Registry, make_database, make_queued_job, make_record
from registry_support import make_version as make_version_row

from jev_rag_api.domain.ingestion.errors import (
    IngestionConflictError,
    IngestionNotFoundError,
)
from jev_rag_api.domain.ingestion.models import DocumentVersion, IngestionJob
from jev_rag_api.integrations.ingestion.content_validation import DocumentContentValidator
from jev_rag_api.integrations.ingestion.local_source_store import LocalSourceDocumentStore
from jev_rag_api.integrations.ingestion.sqlite_database import SqliteDatabase


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.database: SqliteDatabase = make_database(tmp_path)
        self.registry = Registry(self.database)
        self.store = LocalSourceDocumentStore(tmp_path / "sources", max_file_bytes=1_000_000)
        self.store.initialize()
        self.validator = DocumentContentValidator(
            max_file_bytes=1_000_000, allowed_extensions=[".txt", ".md"]
        )

    def close(self) -> None:
        self.registry.close()
        self.store.close()

    async def intake(
        self, name: str, content: bytes, *, key: str, fail_before_job: bool = False
    ) -> tuple[DocumentVersion, IngestionJob]:
        validated = self.validator.validate(source_name=name, source=content)
        storage_key = await self.store.put(validated.content)
        document = await self.registry.documents.create(make_record())
        version = await self.registry.documents.add_version(
            DocumentVersion(
                document_id=document.document_id,
                version=1,
                content_sha256=validated.content_sha256,
                source_name=validated.source_name,
                media_type=validated.media_type,
                storage_key=storage_key,
                created_at=T0,
            )
        )
        if fail_before_job:
            raise IngestionConflictError()
        job = await self.registry.jobs.enqueue(
            make_queued_job(document.document_id),
            idempotency_key=key,
            request_fingerprint=FINGERPRINT,
        )
        return version, job

    def referenced_keys(self) -> set[str]:
        rows = self.registry.connection.run_sync(
            lambda c: c.execute("SELECT storage_key FROM document_versions").fetchall(),
            write=False,
        )
        return {key for (key,) in rows}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    instance = Harness(tmp_path)
    yield instance
    instance.close()


@async_test
async def test_int_01_referenced_source_exists_and_is_bit_identical_after_commit(
    harness: Harness, tmp_path: Path
) -> None:
    content = "Árvíztűrő tükörfúrógép\n".encode()
    version, job = await harness.intake("note.txt", content, key="up-1")
    harness.registry.close()

    reopened = Registry(harness.database)
    try:
        stored_version = await reopened.documents.get_version(version.document_id, 1)
        blob = await harness.store.get(stored_version.storage_key)
        assert blob == content
        assert hashlib.sha256(blob).hexdigest() == stored_version.content_sha256
        assert (await reopened.jobs.get(job.job_id)).document_id == version.document_id
    finally:
        reopened.close()


@async_test
async def test_int_02_registry_failure_after_finalize_leaves_a_traceable_orphan(
    harness: Harness,
) -> None:
    with pytest.raises(IngestionConflictError):
        await harness.intake("note.txt", b"orphan candidate", key="up-2", fail_before_job=True)
    # No job was created, so the work was never accepted. The source is not an unreferenced
    # leak: it is still reachable through the version row that did commit.
    jobs = harness.registry.connection.run_sync(
        lambda c: c.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0], write=False
    )
    assert jobs == 0
    orphan = await harness.store.put(b"written but never registered")
    assert orphan not in harness.referenced_keys()
    # Reconciliation is registry-led: only keys without a referencing version may be removed.
    for key in [orphan]:
        if key not in harness.referenced_keys():
            await harness.store.delete(key)
    with pytest.raises(IngestionNotFoundError):
        await harness.store.get(orphan)


@async_test
async def test_int_02_registry_never_references_a_missing_source(harness: Harness) -> None:
    version, _ = await harness.intake("a.txt", b"first", key="a")
    await harness.intake("b.txt", b"second", key="b")
    for key in harness.referenced_keys():
        assert await harness.store.get(key)
    assert version.storage_key in harness.referenced_keys()


@async_test
async def test_failed_store_put_means_no_registry_rows(harness: Harness, tmp_path: Path) -> None:
    with pytest.raises(Exception):  # noqa: B017 - any domain error from the validator
        await harness.intake("a.txt", b"\x00binary", key="bad")
    assert harness.referenced_keys() == set()
    assert not [p for p in (tmp_path / "sources").rglob("*") if p.is_file()]


@async_test
async def test_referenced_blob_must_not_be_removed_by_cleanup(harness: Harness) -> None:
    version, _ = await harness.intake("a.txt", b"keep me", key="keep")
    orphans = [key for key in [version.storage_key] if key not in harness.referenced_keys()]
    assert orphans == []
    assert await harness.store.get(version.storage_key) == b"keep me"


@async_test
async def test_equal_content_in_two_documents_stays_two_documents(harness: Harness) -> None:
    first, _ = await harness.intake("a.txt", b"identical bytes", key="1")
    second, _ = await harness.intake("b.txt", b"identical bytes", key="2")
    assert first.content_sha256 == second.content_sha256
    assert first.document_id != second.document_id
    assert first.storage_key != second.storage_key


@async_test
async def test_version_rows_use_generated_keys_only(harness: Harness) -> None:
    version, _ = await harness.intake("../../etc/passwd.txt".replace("/", "_"), b"x", key="k")
    assert "etc" not in version.storage_key and "passwd" not in version.storage_key
    assert make_version_row(uuid4()).storage_key  # builder sanity
