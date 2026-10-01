"""Read models assembled by services and mapped to API responses by controllers."""

from dataclasses import dataclass

from onboardx.domain.entities import (
    CaseProfile,
    Decision,
    Override,
    RiskAssessment,
    ScreeningResult,
    StateHistoryEntry,
)


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


@dataclass(frozen=True)
class ReviewQueueItem:
    case_id: str
    product: str
    reason_code: str
    age_minutes: int
    entered_review_at: str


@dataclass(frozen=True)
class OverrideResult:
    case_id: str
    state: str
    override: Override
    account_number: str | None


@dataclass(frozen=True)
class WatchlistEntryView:
    """A watchlist entry with its derived active flag (append-only: deactivation is a row)."""

    entry_id: str
    name: str
    aliases: tuple[str, ...]
    list_type: str
    active: bool
    added_at: str
    deactivated_at: str | None


@dataclass(frozen=True)
class WatchlistPage:
    watchlist_version: int
    items: tuple[WatchlistEntryView, ...]


@dataclass(frozen=True)
class AccountView:
    case_id: str
    product: str
    account_number: str
    created_at: str


@dataclass(frozen=True)
class EvidenceView:
    case_id: str
    state: str
    product: str
    documents: tuple["DocumentView", ...]
    screening: ScreeningResult | None
    risk_assessment: RiskAssessment | None
    decision: Decision | None
    override: Override | None
    review_reason_code: str | None
    account_number_masked: str | None
    history: tuple[StateHistoryEntry, ...]


@dataclass(frozen=True)
class UserView:
    user_id: str
    username: str
    role: str
    active: bool
    created_at: str


@dataclass(frozen=True)
class ChecklistItemSpec:
    item_code: str
    mandatory: bool
    accepted_classes: tuple[str, ...]


@dataclass(frozen=True)
class ChecklistVersionView:
    product: str
    version: int
    created_at: str
    items: tuple[ChecklistItemSpec, ...]


@dataclass(frozen=True)
class QueryResponseView:
    response_id: str
    author: str
    message: str
    created_at: str


@dataclass(frozen=True)
class QueryView:
    query_id: str
    case_id: str
    raised_by: str
    message: str
    status: str
    created_at: str
    responses: tuple[QueryResponseView, ...]
