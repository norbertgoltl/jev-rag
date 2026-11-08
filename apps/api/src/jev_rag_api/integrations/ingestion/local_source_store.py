"""Local filesystem implementation of ``SourceDocumentStore`` (ING-005).

Every operation is relative to a directory file descriptor that is pinned at ``initialize``.
Path components are opened with ``O_NOFOLLOW`` so a planted symlink is never followed, which
removes the check-then-use window of path-string validation. Keys are generated here and never
derived from user input. No I/O happens before ``initialize``.
"""

import asyncio
import os
import re
import secrets
import stat
from pathlib import Path

from jev_rag_api.domain.ingestion.errors import (
    IngestionFileTooLargeError,
    IngestionInternalError,
    IngestionInvalidDocumentError,
    IngestionNotFoundError,
)

# Generated key shape: "<2 hex shard>/<32 hex name>". Anything else is not a key of this store.
_KEY_PATTERN = re.compile(r"^([0-9a-f]{2})/([0-9a-f]{32})$")
_TEMP_PREFIX = ".tmp-"
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600
_MAX_KEY_ATTEMPTS = 8
_READ_CHUNK_BYTES = 1024 * 1024
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class LocalSourceDocumentStore:
    """Stores source bytes under an opaque generated key below one configured root."""

    def __init__(self, root: Path, *, max_file_bytes: int) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        self._configured_root = root
        self._max_file_bytes = max_file_bytes
        self._root_fd: int | None = None

    def initialize(self) -> None:
        """Create the root directory if needed, pin it, and verify it is private enough.

        This is the only place that creates directories. It is idempotent.
        """
        if self._root_fd is not None:
            return
        if not (
            os.open in os.supports_dir_fd
            and os.mkdir in os.supports_dir_fd
            and os.link in os.supports_dir_fd
            and os.unlink in os.supports_dir_fd
        ):
            raise IngestionInternalError()
        configured = self._configured_root
        try:
            if configured.is_symlink():
                raise IngestionInternalError()
            configured.mkdir(mode=_DIRECTORY_MODE, parents=True, exist_ok=True)
            resolved = Path(os.path.realpath(configured))
            fd = os.open(resolved, _DIR_FLAGS)
        except OSError:
            raise IngestionInternalError() from None
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            os.close(fd)
            raise IngestionInternalError()
        self._root_fd = fd

    def close(self) -> None:
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None

    async def put(self, content: bytes) -> str:
        return await asyncio.to_thread(self._put, content)

    async def get(self, storage_key: str) -> bytes:
        return await asyncio.to_thread(self._get, storage_key)

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._delete, storage_key)

    def _require_root(self) -> int:
        if self._root_fd is None:
            raise IngestionInternalError()
        return self._root_fd

    @staticmethod
    def _split_key(storage_key: str) -> tuple[str, str]:
        match = _KEY_PATTERN.fullmatch(storage_key)
        if match is None:
            # Malformed keys (including traversal attempts) can never name a stored source.
            raise IngestionNotFoundError()
        return match.group(1), match.group(2)

    def _put(self, content: bytes) -> str:
        root_fd = self._require_root()
        if not content:
            raise IngestionInvalidDocumentError()
        if len(content) > self._max_file_bytes:
            raise IngestionFileTooLargeError()
        for _ in range(_MAX_KEY_ATTEMPTS):
            name = secrets.token_hex(16)
            shard = name[:2]
            shard_fd = self._open_shard(root_fd, shard, create=True)
            try:
                if self._finalize(shard_fd, name, content):
                    return f"{shard}/{name}"
            finally:
                os.close(shard_fd)
        raise IngestionInternalError()

    def _finalize(self, shard_fd: int, name: str, content: bytes) -> bool:
        """Write a temp file, then publish it without overwriting. False on a name collision."""
        temp_name = f"{_TEMP_PREFIX}{secrets.token_hex(16)}"
        temp_created = False
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                _FILE_MODE,
                dir_fd=shard_fd,
            )
            temp_created = True
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                if os.fstat(handle.fileno()).st_size != len(content):
                    raise IngestionInternalError()
            try:
                # ``link`` fails when the target exists, so no foreign blob is overwritten.
                os.link(
                    temp_name,
                    name,
                    src_dir_fd=shard_fd,
                    dst_dir_fd=shard_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                return False
            os.fsync(shard_fd)
            return True
        except OSError:
            raise IngestionInternalError() from None
        finally:
            if temp_created:
                try:
                    os.unlink(temp_name, dir_fd=shard_fd)
                except OSError:
                    pass

    def _get(self, storage_key: str) -> bytes:
        root_fd = self._require_root()
        shard, name = self._split_key(storage_key)
        shard_fd = self._open_shard(root_fd, shard, create=False)
        try:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=shard_fd)
            except FileNotFoundError:
                raise IngestionNotFoundError() from None
            except OSError:
                raise IngestionInternalError() from None
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > self._max_file_bytes:
                    raise IngestionInternalError()
                return self._read_all(fd)
            except OSError:
                raise IngestionInternalError() from None
            finally:
                os.close(fd)
        finally:
            os.close(shard_fd)

    def _read_all(self, fd: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(fd, _READ_CHUNK_BYTES):
            total += len(chunk)
            if total > self._max_file_bytes:
                raise IngestionInternalError()
            chunks.append(chunk)
        return b"".join(chunks)

    def _delete(self, storage_key: str) -> None:
        root_fd = self._require_root()
        shard, name = self._split_key(storage_key)
        try:
            shard_fd = self._open_shard(root_fd, shard, create=False)
        except IngestionNotFoundError:
            return
        try:
            try:
                os.unlink(name, dir_fd=shard_fd)
                os.fsync(shard_fd)
            except FileNotFoundError:
                return
            except OSError:
                raise IngestionInternalError() from None
        finally:
            os.close(shard_fd)

    @staticmethod
    def _open_shard(root_fd: int, shard: str, *, create: bool) -> int:
        try:
            if create:
                try:
                    os.mkdir(shard, _DIRECTORY_MODE, dir_fd=root_fd)
                except FileExistsError:
                    pass
            return os.open(shard, _DIR_FLAGS, dir_fd=root_fd)
        except FileNotFoundError:
            raise IngestionNotFoundError() from None
        except OSError:
            # Includes a symlink or a regular file where a shard directory must be (tampering).
            raise IngestionInternalError() from None
