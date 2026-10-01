"""AC-02.4a: pure magic-byte validation of uploaded content (VULN-003)."""

import pytest

from onboardx.domain.documents import validate_content
from onboardx.domain.errors import UnsupportedMediaTypeError

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("kind", "content"),
    [
        ("application/pdf", b"%PDF-1.4 synthetic"),
        ("image/jpeg", b"\xff\xd8\xff synthetic"),
        ("image/png", PNG + b"synthetic"),
    ],
)
def test_ac02_4a_matching_signature_is_accepted(kind: str, content: bytes) -> None:
    validate_content(kind, content)


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("kind", "content"),
    [
        ("image/png", b"<html></html>"),
        ("application/pdf", b" %PDF-1.4"),
        ("application/pdf", b"%PDF"),
        ("image/jpeg", b"\xff\xd8"),
        ("image/png", b"\x89PNG\r\n"),
        ("image/png", b"%PDF-1.4"),
        ("image/gif", b"GIF89a"),
        ("application/pdf", b""),
    ],
)
def test_ac02_4a_mismatching_signature_is_415(kind: str, content: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_content(kind, content)
