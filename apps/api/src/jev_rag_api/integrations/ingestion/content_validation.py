"""Content-based validation of uploaded source documents (ING-004).

The validator is HTTP-independent and pure: it reads a bounded input, inspects the real bytes,
and returns an adapter-local result. It never writes files, never logs, and raises only the
stable ``IngestionError`` subclasses. Limits and the accepted encoding policy are documented in
``docs/ingestion/intake-and-persistence.md``.
"""

import hashlib
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import IO, Any, BinaryIO, cast
from xml.etree.ElementTree import Element, ParseError, XMLPullParser

from pydantic import TypeAdapter, ValidationError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from jev_rag_api.domain.ingestion.errors import (
    IngestionFileTooLargeError,
    IngestionInvalidDocumentError,
    IngestionUnsupportedMediaTypeError,
)
from jev_rag_api.domain.ingestion.models import SourceName

TXT_MEDIA_TYPE = "text/plain"
MARKDOWN_MEDIA_TYPE = "text/markdown"
PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Extension -> canonical media type reported on success.
EXTENSION_MEDIA_TYPES: dict[str, str] = {
    ".txt": TXT_MEDIA_TYPE,
    ".md": MARKDOWN_MEDIA_TYPE,
    ".pdf": PDF_MEDIA_TYPE,
    ".docx": DOCX_MEDIA_TYPE,
}

# Extension -> declared media types accepted without a mismatch error.
_ACCEPTED_DECLARED_TYPES: dict[str, frozenset[str]] = {
    ".txt": frozenset({TXT_MEDIA_TYPE}),
    ".md": frozenset({MARKDOWN_MEDIA_TYPE, "text/x-markdown", TXT_MEDIA_TYPE}),
    ".pdf": frozenset({PDF_MEDIA_TYPE}),
    ".docx": frozenset({DOCX_MEDIA_TYPE}),
}
_GENERIC_DECLARED_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})

READ_CHUNK_BYTES = 64 * 1024

# Text policy: strict UTF-8 with an optional BOM. C0 controls other than tab, LF, FF, and CR
# and DEL indicate a binary payload.
_TEXT_ALLOWED_CONTROLS = frozenset({0x09, 0x0A, 0x0C, 0x0D})
_TEXT_INVISIBLE = "﻿​‌‍⁠"

# PDF structure limits.
PDF_EOF_WINDOW_BYTES = 1024
PDF_MAX_PAGES = 10_000

# DOCX (OOXML ZIP) safety limits. Declared sizes are untrusted, so every entry is decompressed
# in bounded chunks and counted.
DOCX_MAX_ENTRIES = 2_000
DOCX_MAX_ENTRY_BYTES = 128 * 1024 * 1024
DOCX_MAX_TOTAL_BYTES = 256 * 1024 * 1024
DOCX_MAX_COMPRESSION_RATIO = 200
DOCX_RATIO_MIN_ENTRY_BYTES = 1024 * 1024
DOCX_MAX_NAME_LENGTH = 255

_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
_RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_DOCUMENT_RELATIONSHIP_SUFFIX = "/officeDocument"
_DOCX_REQUIRED_ENTRIES = ("[Content_Types].xml", "_rels/.rels", "word/document.xml")
_DOCX_FORBIDDEN_ENTRIES = frozenset({"word/vbaproject.bin"})
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_XML_DECLARATIONS = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_SAFE_SOURCE_NAME = TypeAdapter(SourceName)


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    """Adapter-local result of a successful validation. Not a domain model."""

    content: bytes
    size_bytes: int
    content_sha256: str
    media_type: str
    source_name: str


class DocumentContentValidator:
    """Validates source bytes, filename metadata, and the declared media type."""

    def __init__(self, *, max_file_bytes: int, allowed_extensions: Iterable[str]) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        self._max_file_bytes = max_file_bytes
        self._allowed_extensions = frozenset(
            extension for extension in allowed_extensions if extension in EXTENSION_MEDIA_TYPES
        )

    def validate(
        self,
        *,
        source_name: str,
        source: bytes | BinaryIO,
        declared_media_type: str | None = None,
        declared_size: int | None = None,
    ) -> ValidatedDocument:
        """Validate one document.

        ``declared_size`` is only a pre-filter. The enforced limit is the number of bytes
        actually read.
        """
        extension = self._check_metadata(source_name)
        self._check_declared_media_type(extension, declared_media_type)
        if declared_size is not None and declared_size > self._max_file_bytes:
            raise IngestionFileTooLargeError()
        content = self._read_bounded(source)
        if not content:
            raise IngestionInvalidDocumentError()
        _CONTENT_CHECKS[extension](content)
        return ValidatedDocument(
            content=content,
            size_bytes=len(content),
            content_sha256=hashlib.sha256(content).hexdigest(),
            media_type=EXTENSION_MEDIA_TYPES[extension],
            source_name=source_name,
        )

    def _check_metadata(self, source_name: str) -> str:
        try:
            _SAFE_SOURCE_NAME.validate_python(source_name)
        except ValidationError:
            raise IngestionInvalidDocumentError() from None
        extension = PurePosixPath(source_name).suffix.lower()
        if extension not in self._allowed_extensions:
            raise IngestionUnsupportedMediaTypeError()
        return extension

    @staticmethod
    def _check_declared_media_type(extension: str, declared: str | None) -> None:
        if declared is None:
            return
        normalized = declared.split(";", 1)[0].strip().lower()
        if normalized in _GENERIC_DECLARED_TYPES:
            return
        if normalized not in _ACCEPTED_DECLARED_TYPES[extension]:
            raise IngestionUnsupportedMediaTypeError()

    def _read_bounded(self, source: bytes | BinaryIO) -> bytes:
        if isinstance(source, bytes | bytearray | memoryview):
            if len(source) > self._max_file_bytes:
                raise IngestionFileTooLargeError()
            return bytes(source)
        buffer = bytearray()
        while True:
            chunk = source.read(min(READ_CHUNK_BYTES, self._max_file_bytes + 1 - len(buffer)))
            if not chunk:
                return bytes(buffer)
            buffer.extend(chunk)
            if len(buffer) > self._max_file_bytes:
                raise IngestionFileTooLargeError()


def _validate_text(content: bytes) -> None:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestionInvalidDocumentError() from None
    for char in text:
        code = ord(char)
        if (code < 0x20 and code not in _TEXT_ALLOWED_CONTROLS) or code == 0x7F:
            raise IngestionInvalidDocumentError()
    if not text.strip().strip(_TEXT_INVISIBLE).strip():
        raise IngestionInvalidDocumentError()


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(b"%PDF-"):
        raise IngestionInvalidDocumentError()
    tail = content[-PDF_EOF_WINDOW_BYTES:]
    if b"%%EOF" not in tail or b"startxref" not in content[-2 * PDF_EOF_WINDOW_BYTES :]:
        raise IngestionInvalidDocumentError()
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise IngestionInvalidDocumentError()
        page_count = len(reader.pages)
        if page_count < 1 or page_count > PDF_MAX_PAGES:
            raise IngestionInvalidDocumentError()
        reader.pages[0].mediabox  # noqa: B018 - forces the first page object to resolve
    except IngestionInvalidDocumentError:
        raise
    except PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError:
        raise IngestionInvalidDocumentError() from None


def _validate_docx(content: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
            _check_docx_entries(infos)
            _check_docx_payload(archive, infos)
            _check_docx_parts(archive)
    except IngestionInvalidDocumentError:
        raise
    except zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError, EOFError, KeyError:
        raise IngestionInvalidDocumentError() from None
    except RuntimeError, NotImplementedError:
        # Encrypted or unsupported compression raised by ``zipfile``.
        raise IngestionInvalidDocumentError() from None


def _check_docx_entries(infos: list[zipfile.ZipInfo]) -> None:
    if not infos or len(infos) > DOCX_MAX_ENTRIES:
        raise IngestionInvalidDocumentError()
    names: set[str] = set()
    for info in infos:
        name = info.filename
        lowered = name.lower()
        if (
            not name
            or len(name) > DOCX_MAX_NAME_LENGTH
            or "\x00" in name
            or "\\" in name
            or name.startswith("/")
            or _DRIVE_PREFIX.match(name)
            or ".." in name.split("/")
            or lowered in names
            or lowered in _DOCX_FORBIDDEN_ENTRIES
        ):
            raise IngestionInvalidDocumentError()
        names.add(lowered)
        if info.flag_bits & 0x1 or info.compress_type not in {
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
        }:
            raise IngestionInvalidDocumentError()
    if not all(required.lower() in names for required in _DOCX_REQUIRED_ENTRIES):
        raise IngestionInvalidDocumentError()


def _check_docx_payload(archive: zipfile.ZipFile, infos: list[zipfile.ZipInfo]) -> None:
    """Decompress every entry in bounded chunks. Declared sizes are not trusted."""
    total = 0
    for info in infos:
        if info.is_dir():
            continue
        entry_size = 0
        with archive.open(info) as stream:
            while chunk := stream.read(READ_CHUNK_BYTES):
                entry_size += len(chunk)
                total += len(chunk)
                if entry_size > DOCX_MAX_ENTRY_BYTES or total > DOCX_MAX_TOTAL_BYTES:
                    raise IngestionInvalidDocumentError()
        if (
            entry_size >= DOCX_RATIO_MIN_ENTRY_BYTES
            and entry_size > max(info.compress_size, 1) * DOCX_MAX_COMPRESSION_RATIO
        ):
            raise IngestionInvalidDocumentError()


def _check_docx_parts(archive: zipfile.ZipFile) -> None:
    content_types = _read_part(archive, "[Content_Types].xml")
    _require_well_formed(content_types, f"{{{_CONTENT_TYPES_NAMESPACE}}}Types")
    if not _declares_main_part(content_types):
        raise IngestionInvalidDocumentError()
    relationships = _read_part(archive, "_rels/.rels")
    _require_well_formed(relationships, f"{{{_RELATIONSHIPS_NAMESPACE}}}Relationships")
    if not _has_office_document_relationship(relationships):
        raise IngestionInvalidDocumentError()
    with archive.open("word/document.xml") as stream:
        _require_well_formed_stream(stream, f"{{{_WORD_NAMESPACE}}}document")


def _events(parser: XMLPullParser[Any]) -> Iterator[tuple[str, Element]]:
    for item in parser.read_events():
        yield cast("tuple[str, Element]", item)


def _read_part(archive: zipfile.ZipFile, name: str) -> bytes:
    with archive.open(name) as stream:
        return stream.read()


def _require_well_formed(data: bytes, root_tag: str) -> None:
    _require_well_formed_stream(BytesIO(data), root_tag)


def _require_well_formed_stream(stream: IO[bytes], root_tag: str) -> None:
    """Parse incrementally without building the tree. DTDs and entities are rejected."""
    parser: XMLPullParser[Any] = XMLPullParser(events=("start", "end"))
    seen_root = False
    previous_tail = b""
    try:
        while chunk := stream.read(READ_CHUNK_BYTES):
            # The overlap catches a declaration split across two chunks.
            if _XML_DECLARATIONS.search(previous_tail + chunk):
                raise IngestionInvalidDocumentError()
            previous_tail = chunk[-16:]
            parser.feed(chunk)
            for event, element in _events(parser):
                if event == "start" and not seen_root:
                    if element.tag != root_tag:
                        raise IngestionInvalidDocumentError()
                    seen_root = True
                elif event == "end" and element.tag != root_tag:
                    element.clear()
        parser.close()
        for _event, element in _events(parser):
            element.clear()
    except ParseError:
        raise IngestionInvalidDocumentError() from None
    if not seen_root:
        raise IngestionInvalidDocumentError()


def _declares_main_part(content_types: bytes) -> bool:
    parser: XMLPullParser[Any] = XMLPullParser(events=("end",))
    parser.feed(content_types)
    parser.close()
    for _event, element in _events(parser):
        if (
            element.tag == f"{{{_CONTENT_TYPES_NAMESPACE}}}Override"
            and element.get("PartName") == "/word/document.xml"
        ):
            return element.get("ContentType") == _MAIN_CONTENT_TYPE
    return False


def _has_office_document_relationship(relationships: bytes) -> bool:
    parser: XMLPullParser[Any] = XMLPullParser(events=("end",))
    parser.feed(relationships)
    parser.close()
    for _event, element in _events(parser):
        if element.tag == f"{{{_RELATIONSHIPS_NAMESPACE}}}Relationship":
            target = (element.get("Target") or "").lstrip("/")
            relationship_type = element.get("Type") or ""
            if (
                relationship_type.endswith(_OFFICE_DOCUMENT_RELATIONSHIP_SUFFIX)
                and target == "word/document.xml"
            ):
                return True
    return False


_CONTENT_CHECKS = {
    ".txt": _validate_text,
    ".md": _validate_text,
    ".pdf": _validate_pdf,
    ".docx": _validate_docx,
}
