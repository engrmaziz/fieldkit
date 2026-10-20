"""Test suite for magic-byte file validation in DocAI ingestion."""

from __future__ import annotations

import io

import pytest
from fieldkit_docai.pipeline.classify import (
    DocumentTypeException,
    detect_mime_type,
    validate_magic_bytes,
)
from PIL import Image


def test_valid_pdf_magic_bytes() -> None:
    pdf_content = b"%PDF-1.7\n%\xc7\xec\x8f\xa2\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    mime = validate_magic_bytes(pdf_content)
    assert mime == "application/pdf"
    assert detect_mime_type(pdf_content) == "application/pdf"


def test_valid_png_magic_bytes() -> None:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="white")
    img.save(buf, format="PNG")
    png_content = buf.getvalue()

    mime = validate_magic_bytes(png_content)
    assert mime == "image/png"


def test_valid_jpeg_magic_bytes() -> None:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(buf, format="JPEG")
    jpg_content = buf.getvalue()

    mime = validate_magic_bytes(jpg_content)
    assert mime == "image/jpeg"


def test_valid_tiff_magic_bytes() -> None:
    # Little-endian TIFF header
    tiff_le = b"II*\x00\x08\x00\x00\x00"
    assert validate_magic_bytes(tiff_le) == "image/tiff"

    # Big-endian TIFF header
    tiff_be = b"MM\x00*\x00\x00\x00\x08"
    assert validate_magic_bytes(tiff_be) == "image/tiff"


def test_reject_exe_disguised_as_pdf() -> None:
    # DOS/PE executable header disguised as PDF
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    with pytest.raises(DocumentTypeException) as exc_info:
        validate_magic_bytes(fake_pdf)
    assert "Unsupported or invalid document magic bytes" in str(exc_info.value)


def test_reject_shell_script() -> None:
    sh_content = b"#!/bin/bash\necho 'Malicious execution'\n"
    with pytest.raises(DocumentTypeException):
        validate_magic_bytes(sh_content)


def test_reject_empty_content() -> None:
    with pytest.raises(DocumentTypeException):
        validate_magic_bytes(b"")


def test_reject_plain_text() -> None:
    plain = b"This is just plain text, not a supported document format."
    with pytest.raises(DocumentTypeException):
        validate_magic_bytes(plain)
