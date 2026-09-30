"""E2-S1 / AC-02: upload validation, file-name sanitising and per-item status derivation."""

import pytest

from onboardx.domain.documents import (
    MAX_DISPLAY_NAME,
    MAX_UPLOAD_BYTES,
    action_required,
    blocking_items,
    build_item_views,
    normalise_content_type,
    sanitise_filename,
    validate_upload,
)
from onboardx.domain.entities import Checklist, ChecklistItem
from onboardx.domain.enums import Product
from onboardx.domain.errors import FileTooLargeError, UnsupportedMediaTypeError, ValidationError
from onboardx.domain.views import DocumentView


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("..\\..\\windows\\system32\\evil.png", "evil.png"),
        ("/abs/path/file.jpg", "file.jpg"),
        ("C:\\Users\\x\\scan.pdf", "scan.pdf"),
        ("pan_valid.pdf", "pan_valid.pdf"),
        ("utility-bill_1.pdf", "utility-bill_1.pdf"),
        ("na me<>|.pdf", "na me___.pdf"),
        ("evil\x00.pdf", "evil.pdf"),
        ("...", "file"),
        ("", "file"),
        ("   ", "file"),
        ("a/", "file"),
    ],
)
def test_ac02_5_sanitise_filename_keeps_a_safe_basename(raw: str, expected: str) -> None:
    """AC-02.5: only a safe basename survives; traversal components are dropped."""
    assert sanitise_filename(raw) == expected


@pytest.mark.ac("AC-02")
def test_ac02_5_sanitised_name_is_never_longer_than_100_and_keeps_extension() -> None:
    """data-models 3.5: display_name is at most 100 chars; the extension is preserved."""
    cleaned = sanitise_filename("x" * 300 + ".pdf")
    assert len(cleaned) == MAX_DISPLAY_NAME and cleaned.endswith(".pdf")
    assert len(sanitise_filename("y" * 300)) == MAX_DISPLAY_NAME


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    "name", ["../../x.pdf", "a\\b\\c.png", "..", "/", "\\\\server\\share\\f.jpg"]
)
def test_ac02_5_sanitised_name_has_no_separators_or_dot_dot(name: str) -> None:
    """AC-02.5: no path separators remain in any sanitised name."""
    cleaned = sanitise_filename(name)
    assert "/" not in cleaned and "\\" not in cleaned and cleaned not in {"..", "."}


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("content_type", "filename", "expected"),
    [
        ("application/pdf", "a.pdf", "application/pdf"),
        ("image/jpeg", "a.jpg", "image/jpeg"),
        ("image/jpeg", "a.JPEG", "image/jpeg"),
        ("image/png", "a.png", "image/png"),
        ("IMAGE/PNG; charset=binary", "a.png", "image/png"),
    ],
)
def test_ac02_4_validate_upload_accepts_pdf_jpg_png(
    content_type: str, filename: str, expected: str
) -> None:
    """AC-02.4: PDF, JPG and PNG are accepted and the normalised type is returned."""
    assert validate_upload(content_type, filename, 10) == expected


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    ("content_type", "filename"),
    [
        ("text/plain", "a.txt"),
        ("application/zip", "a.zip"),
        ("image/gif", "a.gif"),
        (None, "a.pdf"),
        ("application/pdf", "a.png"),
        ("image/png", "a.jpg"),
        ("application/pdf", "noextension"),
        ("application/x-msdownload", "a.pdf"),
    ],
)
def test_ac02_4_validate_upload_rejects_other_types_with_415(
    content_type: str | None, filename: str
) -> None:
    """AC-02.4: a disallowed or inconsistent type raises UnsupportedMediaTypeError (415)."""
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload(content_type, filename, 10)


@pytest.mark.ac("AC-02")
def test_ac02_4_size_limit_boundary_is_exactly_five_mebibytes() -> None:
    """AC-02.4: 5 MiB is accepted, one byte more is FileTooLargeError (413)."""
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024
    assert validate_upload("application/pdf", "a.pdf", MAX_UPLOAD_BYTES) == "application/pdf"
    with pytest.raises(FileTooLargeError) as excinfo:
        validate_upload("application/pdf", "a.pdf", MAX_UPLOAD_BYTES + 1)
    assert excinfo.value.details == {"max_bytes": MAX_UPLOAD_BYTES}


@pytest.mark.ac("AC-02")
def test_ac02_4_empty_file_is_a_validation_error() -> None:
    """data-models 3.5: size_bytes is at least 1, so an empty file is refused."""
    with pytest.raises(ValidationError):
        validate_upload("application/pdf", "a.pdf", 0)


@pytest.mark.ac("AC-02")
def test_ac02_4_type_is_checked_before_size() -> None:
    """A huge file of a wrong type is 415, not 413."""
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload("text/plain", "a.txt", MAX_UPLOAD_BYTES + 1)


@pytest.mark.ac("AC-02")
def test_ac02_normalise_content_type_handles_none_and_parameters() -> None:
    assert normalise_content_type(None) == ""
    assert normalise_content_type(" Image/PNG ; x=y") == "image/png"


CHECKLIST = Checklist(
    Product.SAVINGS,
    1,
    (
        ChecklistItem("ID_PROOF", True, ("PAN", "AADHAAR", "PASSPORT")),
        ChecklistItem("ADDRESS_PROOF", True, ("AADHAAR", "PASSPORT", "UTILITY_BILL")),
        ChecklistItem("PHOTOGRAPH", False, ("PHOTOGRAPH",)),
    ),
)


def view(item: str, status: str, reason: str | None = None, version: int = 1) -> DocumentView:
    return DocumentView(
        f"doc-{item}", item, version, status, "PAN", reason, 9500, 1, False, 10, "0" * 64, "t"
    )


@pytest.mark.ac("AC-02")
def test_ac02_7_items_without_documents_are_missing_and_block_when_mandatory() -> None:
    """AC-02.7: MISSING mandatory items are listed; optional ones do not block."""
    views = build_item_views(CHECKLIST, [])
    assert [v.status for v in views] == ["MISSING"] * 3
    assert blocking_items(views) == ["ID_PROOF", "ADDRESS_PROOF"]


@pytest.mark.ac("AC-02")
def test_ac02_6_verified_and_flagged_documents_do_not_block_submission() -> None:
    """DD-9: VERIFIED and FLAGGED count as present; REJECTED blocks."""
    views = build_item_views(
        CHECKLIST,
        [view("ID_PROOF", "VERIFIED"), view("ADDRESS_PROOF", "FLAGGED", "DOC_UNRECOGNISED")],
    )
    assert blocking_items(views) == []
    rejected = build_item_views(CHECKLIST, [view("ID_PROOF", "REJECTED", "DOC_EXPIRED")])
    assert blocking_items(rejected) == ["ID_PROOF", "ADDRESS_PROOF"]


@pytest.mark.ac("AC-09")
def test_ac09_3e_action_required_lists_missing_flagged_and_rejected_with_reasons() -> None:
    """AC-09.3e: MISSING (mandatory), FLAGGED and REJECTED items with their reason codes."""
    views = build_item_views(
        CHECKLIST,
        [view("ID_PROOF", "VERIFIED"), view("PHOTOGRAPH", "REJECTED", "DOC_ILLEGIBLE")],
    )
    actions = {a.item_code: (a.status, a.reason_code) for a in action_required(views)}
    assert actions == {
        "ADDRESS_PROOF": ("MISSING", None),
        "PHOTOGRAPH": ("REJECTED", "DOC_ILLEGIBLE"),
    }


@pytest.mark.ac("AC-09")
def test_ac09_3d_verified_replacement_clears_action_required() -> None:
    """AC-09.3d: once every item is VERIFIED nothing is left to do."""
    docs = [view(i.item_code, "VERIFIED") for i in CHECKLIST.items]
    assert action_required(build_item_views(CHECKLIST, docs)) == ()


@pytest.mark.ac("AC-02")
def test_ac02_optional_missing_item_is_not_action_required() -> None:
    """A missing non-mandatory item never appears in action_required."""
    views = build_item_views(
        CHECKLIST, [view("ID_PROOF", "VERIFIED"), view("ADDRESS_PROOF", "VERIFIED")]
    )
    assert action_required(views) == ()


@pytest.mark.ac("AC-09")
def test_ac09_item_view_carries_document_fields() -> None:
    """CaseItemView exposes document_id, doc_version, doc_class and reason_code."""
    (first, *_rest) = build_item_views(
        CHECKLIST, [view("ID_PROOF", "FLAGGED", "DOC_CLASS_MISMATCH", 3)]
    )
    assert (first.document_id, first.doc_version, first.doc_class, first.reason_code) == (
        "doc-ID_PROOF",
        3,
        "PAN",
        "DOC_CLASS_MISMATCH",
    )
