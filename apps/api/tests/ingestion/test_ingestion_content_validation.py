import hashlib
import zipfile
from io import BytesIO

import pytest
from document_samples import (
    CONTENT_TYPES,
    DOCUMENT_XML,
    MACRO_TYPE,
    MAIN_TYPE,
    RELS,
    make_docx,
    make_pdf,
    make_zip,
)

from jev_rag_api.domain.ingestion.errors import (
    IngestionFileTooLargeError,
    IngestionInvalidDocumentError,
    IngestionUnsupportedMediaTypeError,
)
from jev_rag_api.integrations.ingestion import content_validation
from jev_rag_api.integrations.ingestion.content_validation import (
    DOCX_MEDIA_TYPE,
    DocumentContentValidator,
)

ALL_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")


def make_validator(max_file_bytes: int = 1_000_000) -> DocumentContentValidator:
    return DocumentContentValidator(
        max_file_bytes=max_file_bytes, allowed_extensions=ALL_EXTENSIONS
    )


def test_val_01_utf8_text_is_accepted_with_stable_hash() -> None:
    content = "Árvíztűrő tükörfúrógép. The quick brown fox.\n".encode()
    first = make_validator().validate(source_name="note.txt", source=content)
    second = make_validator().validate(source_name="note.txt", source=BytesIO(content))
    assert first.media_type == "text/plain"
    assert first.size_bytes == len(content)
    assert first.content_sha256 == hashlib.sha256(content).hexdigest() == second.content_sha256
    assert first.content == content


def test_val_02_markdown_with_bom_keeps_original_bytes() -> None:
    content = b"\xef\xbb\xbf# C\xc3\xadm\n\n\xc3\x81rv\xc3\xadzt\xc5\xb1r\xc5\x91\n"
    result = make_validator().validate(source_name="README.MD", source=content)
    assert result.media_type == "text/markdown"
    assert result.content == content
    assert result.content_sha256 == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize(
    "content",
    [b"abc\x00def", b"\x01\x02\x03binary", b"caf\xe9 latin-1", b"\xff\xfeh\x00i\x00", b"   \n\t "],
)
@pytest.mark.parametrize("name", ["a.txt", "a.md"])
def test_val_03_binary_or_undecodable_text_is_rejected(name: str, content: bytes) -> None:
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name=name, source=content)


def test_val_04_non_pdf_named_pdf_is_rejected() -> None:
    for content in (b"plain text", make_docx(), b"%PDX-1.4 nope"):
        with pytest.raises(IngestionInvalidDocumentError):
            make_validator().validate(source_name="a.pdf", source=content)


def test_val_05_truncated_or_corrupt_pdf_is_rejected() -> None:
    pdf = make_pdf(pages=2)
    corrupt = [
        pdf[: len(pdf) // 2],
        make_pdf(trailer_eof=False),
        b"%PDF-1.4\n%%EOF\n",
        pdf.replace(b"/Type /Pages", b"/Type /Xages"),
    ]
    for content in corrupt:
        with pytest.raises(IngestionInvalidDocumentError):
            make_validator().validate(source_name="a.pdf", source=content)


def test_val_06_multipage_pdf_is_accepted_without_extraction() -> None:
    pdf = make_pdf(pages=3)
    result = make_validator().validate(source_name="guide.PDF", source=pdf)
    assert result.media_type == "application/pdf"
    assert result.content_sha256 == hashlib.sha256(pdf).hexdigest()


def test_val_07_docx_suffix_without_ooxml_is_rejected() -> None:
    for content in (b"not a zip", make_zip({"hello.txt": b"hi"}), b"PK\x03\x04garbage"):
        with pytest.raises(IngestionInvalidDocumentError):
            make_validator().validate(source_name="a.docx", source=content)


def test_val_08_damaged_docx_is_rejected() -> None:
    good = make_docx()
    damaged = [
        make_docx(omit=("word/document.xml",)),
        make_docx(omit=("_rels/.rels",)),
        make_docx(omit=("[Content_Types].xml",)),
        good[:-30],
        make_docx(document="<w:document"),
        make_docx(document="<root/>"),
        make_docx(content_types=CONTENT_TYPES.format(main=MACRO_TYPE)),
        make_docx(rels=RELS.replace("word/document.xml", "word/other.xml")),
        make_docx(extra={"word/vbaProject.bin": b"macro"}),
    ]
    for content in damaged:
        with pytest.raises(IngestionInvalidDocumentError):
            make_validator().validate(source_name="a.docx", source=content)


def test_docx_is_accepted() -> None:
    result = make_validator().validate(source_name="a.docx", source=make_docx())
    assert result.media_type == DOCX_MEDIA_TYPE


def test_docx_with_dtd_or_entities_is_rejected() -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "&a;</w:document>"
    )
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=make_docx(document=bomb))


def test_docx_dtd_split_across_read_chunks_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_validation, "READ_CHUNK_BYTES", 7)
    document = DOCUMENT_XML.replace("<w:body>", "<!DOCTYPE x><w:body>", 1)
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=make_docx(document=document))


@pytest.mark.parametrize(
    "entry_name", ["../evil.xml", "/abs.xml", "C:evil.xml", "word\\x.xml", "a/../../b.xml"]
)
def test_val_09_unsafe_zip_entry_names_are_rejected(entry_name: str) -> None:
    content = make_docx(extra={entry_name: b"x"})
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=content)


def test_val_09_too_many_entries_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_validation, "DOCX_MAX_ENTRIES", 5)
    content = make_docx(extra={f"word/media/{index}.bin": b"x" for index in range(10)})
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=content)


def test_val_09_decompression_bomb_is_rejected() -> None:
    bomb = make_docx(extra={"word/media/bomb.bin": b"\x00" * (4 * 1024 * 1024)})
    assert len(bomb) < 100_000
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=bomb)


def test_val_09_total_uncompressed_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_validation, "DOCX_MAX_TOTAL_BYTES", 1024)
    content = make_docx(extra={"word/media/a.bin": bytes(range(256)) * 8})
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=content)


def test_docx_duplicate_and_encrypted_entries_are_rejected() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES.format(main=MAIN_TYPE))
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", DOCUMENT_XML)
        with pytest.warns(UserWarning):
            archive.writestr("word/document.xml", DOCUMENT_XML)
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=buffer.getvalue())

    encrypted = bytearray(make_docx())
    # Set the "encrypted" general purpose flag in every local and central directory header.
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = encrypted.find(signature)
        while position != -1:
            encrypted[position + offset] |= 0x01
            position = encrypted.find(signature, position + 1)
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.docx", source=bytes(encrypted))


def test_docx_with_unsupported_compression_is_rejected() -> None:
    entries = {
        "[Content_Types].xml": CONTENT_TYPES.format(main=MAIN_TYPE).encode(),
        "_rels/.rels": RELS.encode(),
        "word/document.xml": DOCUMENT_XML.encode(),
    }
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(
            source_name="a.docx", source=make_zip(entries, compression=zipfile.ZIP_BZIP2)
        )


@pytest.mark.parametrize(
    ("name", "declared"),
    [
        ("a.exe", None),
        ("a.docm", None),
        ("a", None),
        ("archive.tar.gz", None),
        ("a.txt", "application/pdf"),
        ("a.pdf", "text/plain"),
        ("a.docx", "application/vnd.ms-word.document.macroEnabled.12"),
        ("a.txt", "image/png"),
    ],
)
def test_val_10_unsupported_extension_or_media_type_mismatch(
    name: str, declared: str | None
) -> None:
    with pytest.raises(IngestionUnsupportedMediaTypeError):
        make_validator().validate(
            source_name=name, source=b"some text", declared_media_type=declared
        )


@pytest.mark.parametrize(
    ("name", "declared"),
    [
        ("a.txt", "text/plain; charset=utf-8"),
        ("a.txt", "application/octet-stream"),
        ("a.txt", None),
        ("a.md", "text/x-markdown"),
        ("a.md", "TEXT/MARKDOWN"),
    ],
)
def test_declared_media_type_compatible_with_extension_is_accepted(
    name: str, declared: str | None
) -> None:
    result = make_validator().validate(
        source_name=name, source=b"hello", declared_media_type=declared
    )
    assert result.source_name == name


def test_extension_must_be_in_the_configured_allowlist() -> None:
    validator = DocumentContentValidator(max_file_bytes=100, allowed_extensions=[".txt"])
    with pytest.raises(IngestionUnsupportedMediaTypeError):
        validator.validate(source_name="a.pdf", source=make_pdf())


@pytest.mark.parametrize("name", ["", "   ", "a/b.txt", "..\\a.txt", "a\x00.txt", "a\n.txt"])
def test_unsafe_source_names_are_rejected(name: str) -> None:
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name=name, source=b"hello")


def test_val_11_actual_size_is_enforced_regardless_of_declared_size() -> None:
    validator = make_validator(max_file_bytes=100)
    content = b"a" * 101
    with pytest.raises(IngestionFileTooLargeError):
        validator.validate(source_name="a.txt", source=content, declared_size=10)
    with pytest.raises(IngestionFileTooLargeError):
        validator.validate(source_name="a.txt", source=BytesIO(content), declared_size=10)
    with pytest.raises(IngestionFileTooLargeError):
        validator.validate(source_name="a.txt", source=b"a", declared_size=101)
    assert validator.validate(source_name="a.txt", source=b"a" * 100).size_bytes == 100


def test_stream_read_never_exceeds_the_limit_by_more_than_one_byte() -> None:
    class CountingStream(BytesIO):
        total = 0

        def read(self, size: int | None = -1) -> bytes:
            data = super().read(size)
            self.total += len(data)
            return data

    stream = CountingStream(b"a" * 10_000)
    with pytest.raises(IngestionFileTooLargeError):
        make_validator(max_file_bytes=1_000).validate(source_name="a.txt", source=stream)
    assert stream.total <= 1_001


def test_val_12_empty_and_blank_content_are_rejected() -> None:
    for content in (b"", b"\n\n \t", b"\xef\xbb\xbf"):
        with pytest.raises(IngestionInvalidDocumentError):
            make_validator().validate(source_name="a.txt", source=content)
    with pytest.raises(IngestionInvalidDocumentError):
        make_validator().validate(source_name="a.pdf", source=BytesIO(b""))


def test_validator_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        DocumentContentValidator(max_file_bytes=0, allowed_extensions=[".txt"])


def test_validation_errors_do_not_expose_content_or_names() -> None:
    secret = b"TOP-SECRET-\x00-payload"
    with pytest.raises(IngestionInvalidDocumentError) as caught:
        make_validator().validate(source_name="confidential-plan.txt", source=secret)
    rendered = f"{caught.value!s} {caught.value!r} {caught.value.__cause__!r}"
    assert "TOP-SECRET" not in rendered
    assert "confidential" not in rendered
