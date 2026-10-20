"""Test suite for DocAI FastAPI REST endpoints."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from fieldkit_docai.main import app
from PIL import Image

client = TestClient(app)


def test_healthz_and_readyz() -> None:
    res_h = client.get("/healthz")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "healthy"

    res_r = client.get("/readyz")
    assert res_r.status_code == 200
    assert res_r.json()["status"] == "ready"


def test_upload_valid_document() -> None:
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color="white")
    img.save(buf, format="PNG")
    content = buf.getvalue()

    response = client.post(
        "/documents",
        files={"file": ("lieferschein_1001.png", content, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "lieferschein_1001.png"
    assert data["mime_type"] == "image/png"
    assert data["sha256"] != ""

    doc_id = data["document_id"]

    # Verify status endpoint
    res_status = client.get(f"/documents/{doc_id}")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["document_id"] == doc_id


def test_reject_unsupported_file_disguised() -> None:
    fake_pdf = b"MZ\x90\x00Not a valid PDF executable payload"
    response = client.post(
        "/documents",
        files={"file": ("evil.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "Invalid document type: magic bytes mismatch" in response.json()["detail"]


def test_reject_oversized_file() -> None:
    # 51 MB dummy payload to exceed 50 MB limit
    oversized = b"0" * (51 * 1024 * 1024)
    response = client.post(
        "/documents",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]
