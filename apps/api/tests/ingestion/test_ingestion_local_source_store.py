import hashlib
import os
import secrets
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from async_support import async_test

from jev_rag_api.domain.ingestion.errors import (
    IngestionFileTooLargeError,
    IngestionInternalError,
    IngestionInvalidDocumentError,
    IngestionNotFoundError,
)
from jev_rag_api.domain.ingestion.models import DocumentVersion
from jev_rag_api.integrations.ingestion import local_source_store as store_module
from jev_rag_api.integrations.ingestion.local_source_store import LocalSourceDocumentStore

MAX_BYTES = 10_000


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "sources"


@pytest.fixture
def store(root: Path) -> Iterator[LocalSourceDocumentStore]:
    instance = LocalSourceDocumentStore(root, max_file_bytes=MAX_BYTES)
    instance.initialize()
    yield instance
    instance.close()


def all_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())


def test_construction_performs_no_io(tmp_path: Path) -> None:
    target = tmp_path / "never-created"
    LocalSourceDocumentStore(target, max_file_bytes=MAX_BYTES)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


@async_test
async def test_operations_before_initialize_fail_without_io(tmp_path: Path) -> None:
    target = tmp_path / "sources"
    store = LocalSourceDocumentStore(target, max_file_bytes=MAX_BYTES)
    with pytest.raises(IngestionInternalError):
        await store.put(b"data")
    assert not target.exists()


def test_initialize_is_idempotent_and_creates_private_root(root: Path) -> None:
    store = LocalSourceDocumentStore(root, max_file_bytes=MAX_BYTES)
    store.initialize()
    store.initialize()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    store.close()
    store.close()


def test_initialize_rejects_symlinked_or_writable_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(IngestionInternalError):
        LocalSourceDocumentStore(link, max_file_bytes=MAX_BYTES).initialize()

    open_dir = tmp_path / "open"
    open_dir.mkdir()
    open_dir.chmod(0o777)
    with pytest.raises(IngestionInternalError):
        LocalSourceDocumentStore(open_dir, max_file_bytes=MAX_BYTES).initialize()


def test_initialize_rejects_a_file_as_root(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(IngestionInternalError):
        LocalSourceDocumentStore(blocker, max_file_bytes=MAX_BYTES).initialize()


def test_rejects_non_positive_limit(root: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        LocalSourceDocumentStore(root, max_file_bytes=0)


@async_test
async def test_sto_01_round_trip_is_byte_exact(store: LocalSourceDocumentStore) -> None:
    samples = [
        "Árvíztűrő tükörfúrógép — ŐűÖÜ".encode(),
        bytes(range(256)) * 4,
        b"\x00\x00binary\xff",
        b"a",
    ]
    for content in samples:
        key = await store.put(content)
        returned = await store.get(key)
        assert returned == content
        assert hashlib.sha256(returned).digest() == hashlib.sha256(content).digest()


@async_test
async def test_sto_02_keys_are_generated_opaque_and_model_valid(
    store: LocalSourceDocumentStore,
) -> None:
    first = await store.put(b"same bytes")
    second = await store.put(b"same bytes")
    assert first != second
    for key in (first, second):
        assert not key.startswith("/")
        assert ".." not in key.split("/")
        assert "same" not in key
        DocumentVersion(
            document_id="b9d7a2c4-5f31-4b8e-9a64-1c2d3e4f5a6b",  # type: ignore[arg-type]
            version=1,
            content_sha256="a" * 64,
            source_name="note.txt",
            media_type="text/plain",
            storage_key=key,
            created_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "key",
    [
        "../outside",
        "../../etc/passwd",
        "/etc/passwd",
        "ab/../../outside",
        "ab/" + "0" * 31 + "/",
        "AB/" + "0" * 32,
        "ab/" + "0" * 32 + "/extra",
        "ab\\" + "0" * 32,
        "",
        ".",
        "..",
        "ab/.tmp-" + "0" * 24,
    ],
)
@async_test
async def test_sto_03_malformed_and_traversal_keys_are_rejected(
    store: LocalSourceDocumentStore, tmp_path: Path, key: str
) -> None:
    outside = tmp_path / "outside"
    outside.write_text("secret")
    with pytest.raises(IngestionNotFoundError):
        await store.get(key)
    with pytest.raises(IngestionNotFoundError):
        await store.delete(key)
    assert outside.read_text() == "secret"


@async_test
async def test_sto_03_symlinked_shard_directory_is_never_followed(
    store: LocalSourceDocumentStore, root: Path, tmp_path: Path
) -> None:
    victim_dir = tmp_path / "victim"
    victim_dir.mkdir()
    name = "c" * 32
    (victim_dir / name).write_bytes(b"outside data")
    (root / "cc").symlink_to(victim_dir, target_is_directory=True)
    with pytest.raises(IngestionInternalError):
        await store.get(f"cc/{name}")
    with pytest.raises(IngestionInternalError):
        await store.delete(f"cc/{name}")
    assert (victim_dir / name).read_bytes() == b"outside data"


@async_test
async def test_sto_03_symlinked_blob_is_never_followed(
    store: LocalSourceDocumentStore, root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside data")
    name = "d" * 32
    shard = root / "dd"
    shard.mkdir(mode=0o700)
    (shard / name).symlink_to(outside)
    with pytest.raises(IngestionInternalError):
        await store.get(f"dd/{name}")
    await store.delete(f"dd/{name}")  # removes the link itself, never the target
    assert outside.read_bytes() == b"outside data"
    assert not (shard / name).exists() and not (shard / name).is_symlink()


@async_test
async def test_put_does_not_follow_a_symlinked_shard(
    store: LocalSourceDocumentStore, root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim_dir = tmp_path / "victim"
    victim_dir.mkdir()
    (root / "ee").symlink_to(victim_dir, target_is_directory=True)
    monkeypatch.setattr(secrets, "token_hex", lambda _n: "ee" * 16)
    with pytest.raises(IngestionInternalError):
        await store.put(b"payload")
    assert list(victim_dir.iterdir()) == []


@async_test
async def test_sto_04_interrupted_temp_write_leaves_no_visible_blob(
    store: LocalSourceDocumentStore, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_fsync(_fd: int) -> None:
        raise OSError("disk failure at /private/path")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(IngestionInternalError) as caught:
        await store.put(b"partial")
    assert "private" not in repr(caught.value)
    assert all_files(root) == []


@async_test
async def test_sto_04_failed_write_cleans_up_the_temp_file(
    store: LocalSourceDocumentStore, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_fdopen = os.fdopen

    class FailingHandle:
        def __init__(self, handle: object) -> None:
            self._handle = handle

        def __enter__(self) -> FailingHandle:
            return self

        def __exit__(self, *_args: object) -> None:
            self._handle.close()  # type: ignore[attr-defined]

        def write(self, _data: bytes) -> int:
            raise OSError("no space left")

    monkeypatch.setattr(os, "fdopen", lambda fd, mode: FailingHandle(real_fdopen(fd, mode)))
    with pytest.raises(IngestionInternalError):
        await store.put(b"data")
    assert all_files(root) == []


@async_test
async def test_sto_05_name_collision_never_overwrites_another_blob(
    store: LocalSourceDocumentStore, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing_key = await store.put(b"original blob")
    existing_name = existing_key.split("/")[1]
    values = iter([existing_name, "1" * 32, "f" * 32, "2" * 32])
    monkeypatch.setattr(secrets, "token_hex", lambda _n: next(values))
    new_key = await store.put(b"new blob")
    assert new_key != existing_key
    assert await store.get(existing_key) == b"original blob"
    assert await store.get(new_key) == b"new blob"
    assert not [path for path in all_files(root) if path.name.startswith(".tmp-")]


@async_test
async def test_sto_05_persistent_collision_fails_without_a_false_key(
    store: LocalSourceDocumentStore, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing_key = await store.put(b"original blob")
    monkeypatch.setattr(
        secrets,
        "token_hex",
        lambda _n: existing_key.split("/")[1],
    )
    monkeypatch.setattr(store_module, "_MAX_KEY_ATTEMPTS", 3)
    with pytest.raises(IngestionInternalError):
        await store.put(b"intruder")
    assert await store.get(existing_key) == b"original blob"
    assert [path.name for path in all_files(root) if path.name.startswith(".tmp-")] == []


@async_test
async def test_sto_06_get_missing_and_idempotent_delete(store: LocalSourceDocumentStore) -> None:
    key = await store.put(b"to delete")
    await store.delete(key)
    await store.delete(key)
    await store.delete("ab/" + "0" * 32)
    with pytest.raises(IngestionNotFoundError):
        await store.get(key)
    with pytest.raises(IngestionNotFoundError):
        await store.get("ab/" + "0" * 32)


@async_test
async def test_put_enforces_content_rules(store: LocalSourceDocumentStore, root: Path) -> None:
    with pytest.raises(IngestionInvalidDocumentError):
        await store.put(b"")
    with pytest.raises(IngestionFileTooLargeError):
        await store.put(b"x" * (MAX_BYTES + 1))
    assert all_files(root) == []
    assert await store.get(await store.put(b"x" * MAX_BYTES)) == b"x" * MAX_BYTES


@async_test
async def test_files_and_directories_are_private(
    store: LocalSourceDocumentStore, root: Path
) -> None:
    key = await store.put(b"private")
    shard, name = key.split("/")
    assert stat.S_IMODE((root / shard).stat().st_mode) == 0o700
    assert stat.S_IMODE((root / shard / name).stat().st_mode) == 0o600


@async_test
async def test_get_rejects_a_blob_that_grew_beyond_the_limit(
    store: LocalSourceDocumentStore, root: Path
) -> None:
    key = await store.put(b"small")
    (root / key).write_bytes(b"y" * (MAX_BYTES + 1))
    with pytest.raises(IngestionInternalError):
        await store.get(key)


@async_test
async def test_get_rejects_a_directory_in_place_of_a_blob(
    store: LocalSourceDocumentStore, root: Path
) -> None:
    key = await store.put(b"small")
    (root / key).unlink()
    (root / key).mkdir()
    with pytest.raises(IngestionInternalError):
        await store.get(key)


@async_test
async def test_no_temp_files_remain_after_success(
    store: LocalSourceDocumentStore, root: Path
) -> None:
    await store.put(b"one")
    await store.put(b"two")
    assert [path for path in all_files(root) if path.name.startswith(".tmp-")] == []
