"""Read models assembled by services and mapped to API responses by controllers."""

from dataclasses import dataclass

from onboardx.domain.entities import CaseProfile, Decision


@dataclass(frozen=True)
class CaseItemView:
    item_code: str
    mandatory: bool
    accepted_classes: tuple[str, ...]
    status: str
    document_id: str | None
    doc_version: int | None
    doc_class: str | None
    reason_code: str | None


@dataclass(frozen=True)
class ActionRequired:
    item_code: str
    status: str
    reason_code: str | None


@dataclass(frozen=True)
class CaseDetail:
    case_id: str
    name: str
    contact_masked: str
    product: str
    state: str
    checklist_version: int
    checklist_items: tuple[CaseItemView, ...]
    missing_items: tuple[str, ...]
    action_required: tuple[ActionRequired, ...]
    profile: CaseProfile | None
    profile_complete: bool
    account_number_masked: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CaseListItem:
    case_id: str
    product: str
    state: str
    age_minutes: int
    created_at: str


@dataclass(frozen=True)
class CaseListPage:
    items: tuple[CaseListItem, ...]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class DocumentView:
    """A stored document version with its derived status (REJECTED overlays the classifier)."""

    document_id: str
    checklist_item: str
    version: int
    status: str
    doc_class: str
    reason_code: str | None
    confidence_bp: int
    rule_version: int
    superseded: bool
    size_bytes: int
    sha256: str
    uploaded_at: str


@dataclass(frozen=True)
class DecisionResult:
    case_id: str
    state: str
    decision: Decision
    account_number: str | None


@dataclass(frozen=True)
class AdvanceResult:
    case_id: str
    state: str
    steps_run: tuple[str, ...]
    decision: Decision | None


@dataclass(frozen=True)
class SubmitResult:
    case_id: str
    state: str
    missing_items: tuple[str, ...]
