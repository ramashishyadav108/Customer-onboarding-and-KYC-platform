"""Frozen dataclasses for persisted domain entities (timestamps are ISO-8601 UTC strings)."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from onboardx.domain.enums import CaseState, Product, Role
from onboardx.domain.risk import FactorScore


@dataclass(frozen=True)
class User:
    user_id: str
    username: str
    password_hash: str
    role: Role
    case_id: str | None


@dataclass(frozen=True)
class Case:
    case_id: str
    name: str
    contact: str
    product: Product
    state: CaseState
    checklist_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CaseProfile:
    case_id: str
    date_of_birth: date
    annual_income: int
    occupation_category: str
    country_code: str
    state_code: str | None
    updated_at: str


@dataclass(frozen=True)
class ChecklistItem:
    item_code: str
    mandatory: bool
    accepted_classes: tuple[str, ...]


@dataclass(frozen=True)
class Checklist:
    product: Product
    version: int
    items: tuple[ChecklistItem, ...]


@dataclass(frozen=True)
class StateHistoryEntry:
    history_id: str
    case_id: str
    from_state: CaseState | None
    to_state: CaseState
    actor: str
    reason_code: str | None
    idempotency_key: str | None
    created_at: str


@dataclass(frozen=True)
class AuditEntry:
    audit_id: str
    case_id: str | None
    event: str
    actor: str
    role: str
    payload: dict[str, Any]
    correlation_id: str
    created_at: str


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of OnboardingService.transition; ``replayed`` marks an idempotent repeat."""

    case_id: str
    from_state: CaseState | None
    to_state: CaseState
    history_id: str
    created_at: str
    replayed: bool = False


@dataclass(frozen=True)
class Document:
    """One stored file version; ``display_name`` and ``storage_path`` are never logged."""

    document_id: str
    case_id: str
    checklist_item: str
    version: int
    storage_path: str
    display_name: str
    content_type: str
    sha256: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: str


@dataclass(frozen=True)
class ClassificationResult:
    result_id: str
    document_id: str
    doc_class: str
    status: str
    reason_code: str | None
    confidence_bp: int
    rule_version: int
    classified_at: str


@dataclass(frozen=True)
class DocumentRejection:
    rejection_id: str
    document_id: str
    case_id: str
    reason_code: str
    comment: str | None
    actor: str
    created_at: str


@dataclass(frozen=True)
class WatchlistEntry:
    entry_id: str
    name: str
    aliases: tuple[str, ...]
    list_type: str
    name_tokens: str
    alias_tokens: tuple[str, ...]


@dataclass(frozen=True)
class ScreeningResult:
    result_id: str
    case_id: str
    hits: tuple[dict[str, str], ...]
    requires_manual_review: bool
    watchlist_version: int
    screened_at: str


@dataclass(frozen=True)
class RiskAssessment:
    assessment_id: str
    case_id: str
    score: int
    band: str
    rule_version: int
    source: str
    breakdown: tuple[FactorScore, ...]
    created_at: str


@dataclass(frozen=True)
class Decision:
    decision_id: str
    case_id: str
    outcome: str
    reason_code: str
    rule_version: int
    actor: str
    created_at: str


@dataclass(frozen=True)
class Override:
    override_id: str
    case_id: str
    actor: str
    decision: str
    reason_code: str
    comment: str | None
    rule_version: int
    created_at: str


@dataclass(frozen=True)
class Account:
    account_id: str
    case_id: str
    product: Product
    account_number: str
    created_at: str


@dataclass(frozen=True)
class Notification:
    notification_id: str
    case_id: str
    event: str
    template: str
    text: str
    details: dict[str, str]
    contact_masked: str
    created_at: str


STAFF_ROLES = frozenset({Role.KYC_ANALYST, Role.COMPLIANCE_OFFICER, Role.ADMIN})
