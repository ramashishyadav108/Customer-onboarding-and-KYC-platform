"""Upload rules, file-name sanitising and per-item status derivation (AC-02, AC-09)."""

import re
from collections.abc import Iterable, Sequence

from onboardx.domain.entities import Checklist, ChecklistItem
from onboardx.domain.enums import ItemStatus
from onboardx.domain.errors import FileTooLargeError, UnsupportedMediaTypeError, ValidationError
from onboardx.domain.views import ActionRequired, CaseItemView, DocumentView

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DISPLAY_NAME = 100
STORED_EXTENSION = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
_EXTENSIONS = {
    "application/pdf": frozenset({"pdf"}),
    "image/jpeg": frozenset({"jpg", "jpeg"}),
    "image/png": frozenset({"png"}),
}
_SIGNATURES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": bytes.fromhex("ffd8ff"),
    "image/png": bytes.fromhex("89504e470d0a1a0a"),
}
_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]")
_BLOCKING = frozenset({str(ItemStatus.MISSING), str(ItemStatus.REJECTED)})
_ACTIONABLE = _BLOCKING | {str(ItemStatus.FLAGGED)}


def sanitise_filename(name: str) -> str:
    """Basename only, unsafe characters replaced, at most 100 chars; never empty or dot-only."""
    base = re.split(r"[\\/]", name.replace("\x00", ""))[-1]
    cleaned = _UNSAFE.sub("_", base).strip(" .")
    if len(cleaned) > MAX_DISPLAY_NAME:
        stem, dot, ext = cleaned.rpartition(".")
        if dot and 0 < len(ext) <= 5:
            cleaned = stem[: MAX_DISPLAY_NAME - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:MAX_DISPLAY_NAME]
    return cleaned or "file"


def normalise_content_type(value: str | None) -> str:
    return (value or "").split(";")[0].strip().lower()


def validate_upload(content_type: str | None, filename: str, size_bytes: int) -> str:
    """Return the normalised content type or raise 415 / 413 / 422 (empty file)."""
    kind = normalise_content_type(content_type)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if kind not in _EXTENSIONS or extension not in _EXTENSIONS[kind]:
        raise UnsupportedMediaTypeError
    if size_bytes > MAX_UPLOAD_BYTES:
        raise FileTooLargeError(MAX_UPLOAD_BYTES)
    if size_bytes < 1:
        raise ValidationError.single("file", "file must not be empty")
    return kind


def validate_content(kind: str, content: bytes) -> None:
    """Pure magic-byte check: the content must start with the signature of its declared type."""
    signature = _SIGNATURES.get(kind)
    if signature is None or not content.startswith(signature):
        raise UnsupportedMediaTypeError


def _item_view(item: ChecklistItem, doc: DocumentView | None) -> CaseItemView:
    if doc is None:
        return CaseItemView(
            item.item_code,
            item.mandatory,
            item.accepted_classes,
            str(ItemStatus.MISSING),
            None,
            None,
            None,
            None,
        )
    return CaseItemView(
        item.item_code,
        item.mandatory,
        item.accepted_classes,
        doc.status,
        doc.document_id,
        doc.version,
        doc.doc_class,
        doc.reason_code,
    )


def build_item_views(
    checklist: Checklist, current: Sequence[DocumentView]
) -> tuple[CaseItemView, ...]:
    """One view per checklist item; MISSING when no current document exists."""
    by_item = {doc.checklist_item: doc for doc in current}
    return tuple(_item_view(item, by_item.get(item.item_code)) for item in checklist.items)


def blocking_items(views: Iterable[CaseItemView]) -> list[str]:
    """Mandatory items with no acceptable document: MISSING or REJECTED (DD-9)."""
    return [v.item_code for v in views if v.mandatory and v.status in _BLOCKING]


def action_required(views: Iterable[CaseItemView]) -> tuple[ActionRequired, ...]:
    """Items the prospect must act on: mandatory MISSING, or any FLAGGED / REJECTED item."""
    return tuple(
        ActionRequired(v.item_code, v.status, v.reason_code)
        for v in views
        if v.status in _ACTIONABLE and (v.mandatory or v.status != str(ItemStatus.MISSING))
    )
