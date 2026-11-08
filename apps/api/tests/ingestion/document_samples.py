"""Deterministic, offline sample documents for ingestion adapter tests."""

import zipfile
from io import BytesIO

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="{main}"/>'
    "</Types>"
)
MAIN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
MACRO_TYPE = "application/vnd.ms-word.document.macroEnabled.main+xml"
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)
DOCUMENT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>Árvíztűrő tükörfúrógép</w:t></w:r></w:p></w:body></w:document>"
)


def make_pdf(pages: int = 1, *, trailer_eof: bool = True) -> bytes:
    """Build a small, valid PDF with ``pages`` text pages and a correct xref table."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    for index in range(pages):
        page_number = 3 + index * 2
        content_number = page_number + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            f"/Contents {content_number} 0 R /Resources << /Font << /F1 "
            f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 20 100 Td (Page {index + 1}) Tj ET".encode()
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    body = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(body)
    body += f"xref\n0 {len(objects) + 1}\n".encode()
    body += b"0000000000 65535 f \n"
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode()
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n".encode()
    )
    if trailer_eof:
        body += b"%%EOF\n"
    return bytes(body)


def make_docx(
    *,
    content_types: str | None = None,
    rels: str = RELS,
    document: str | bytes = DOCUMENT_XML,
    extra: dict[str, bytes] | None = None,
    omit: tuple[str, ...] = (),
) -> bytes:
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types or CONTENT_TYPES.format(main=MAIN_TYPE),
        "_rels/.rels": rels,
        "word/document.xml": document,
    }
    for name in omit:
        parts.pop(name)
    parts.update(extra or {})
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def make_zip(entries: dict[str, bytes], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, data in entries.items():
            archive.writestr(zipfile.ZipInfo(name), data, compress_type=compression)
    return buffer.getvalue()
