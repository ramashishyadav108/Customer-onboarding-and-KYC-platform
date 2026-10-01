"""AC-02.4a (VULN-003): upload content must match the declared type by magic bytes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import create_lead
from pipeline_helpers import PDF_BYTES, rows, upload

HTML = b"<html><script>alert(1)</script></html>"
PNG_BYTES = b"\x89PNG\r\n\x1a\n synthetic fixture"
JPEG_BYTES = b"\xff\xd8\xff synthetic fixture"


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("pan_valid.png", "image/png"),
        ("pan_valid.jpg", "image/jpeg"),
        ("pan_valid.pdf", "application/pdf"),
    ],
)
def test_ac02_4a_html_declared_as_an_allowed_type_is_415_and_not_stored(
    client: TestClient, engine: Engine, upload_dir: Path, filename: str, content_type: str
) -> None:
    response = upload(client, create_lead(client), "ID_PROOF", filename, HTML, content_type)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert rows(engine, "SELECT COUNT(*) FROM documents")[0][0] == 0
    assert not upload_dir.exists() or [p for p in upload_dir.rglob("*") if p.is_file()] == []


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("filename", "content"),
    [("pan_valid.png", PDF_BYTES), ("pan_valid.jpg", PNG_BYTES), ("pan_valid.pdf", JPEG_BYTES)],
)
def test_ac02_4a_real_content_of_a_different_type_is_415(
    client: TestClient, filename: str, content: bytes
) -> None:
    response = upload(client, create_lead(client), "ID_PROOF", filename, content)
    assert response.status_code == 415


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("filename", "content"),
    [("pan_valid.png", PNG_BYTES), ("pan_valid.jpg", JPEG_BYTES), ("pan_valid.pdf", PDF_BYTES)],
)
def test_ac02_4a_content_matching_its_declared_type_is_201(
    client: TestClient, filename: str, content: bytes
) -> None:
    response = upload(client, create_lead(client), "ID_PROOF", filename, content)
    assert response.status_code == 201
