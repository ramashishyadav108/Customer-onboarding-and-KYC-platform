"""Document, submission, pipeline-step and notification schemas (api-contracts 2.3 - 2.5)."""

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field

from onboardx.domain.entities import (
    Decision,
    DocumentRejection,
    Notification,
    RiskAssessment,
    ScreeningResult,
)
from onboardx.domain.views import AdvanceResult, DecisionResult, DocumentView, SubmitResult


class UploadResponse(BaseModel):
    document_id: str
    checklist_item: str
    version: int
    doc_class: str
    status: str
    reason_code: str | None
    confidence_bp: int
    rule_version: int


class DocumentViewOut(UploadResponse):
    superseded: bool
    size_bytes: int
    sha256: str
    uploaded_at: str


class DocumentListOut(BaseModel):
    case_id: str
    documents: list[DocumentViewOut]


class RejectRequest(BaseModel):
    reason_code: str
    comment: str | None = Field(default=None, max_length=500)


class RejectResponse(BaseModel):
    document_id: str
    status: str
    reason_code: str


class SubmitOut(BaseModel):
    case_id: str
    state: str
    missing_items: list[str]


class HitOut(BaseModel):
    entry_id: str
    list_type: str
    reason_code: str


class ScreeningOut(BaseModel):
    id: str
    case_id: str
    hits: list[HitOut]
    requires_manual_review: bool
    watchlist_version: int
    screened_at: str


class ScreenResponse(BaseModel):
    state: str
    result: ScreeningOut


class FactorOut(BaseModel):
    factor: str
    value_label: str
    points: int
    weight: int
    contribution: int


class AssessmentOut(BaseModel):
    assessment_id: str
    case_id: str
    score: int
    band: str
    rule_version: int
    source: str
    breakdown: list[FactorOut]
    created_at: str


class ClassifyResponse(BaseModel):
    case_id: str
    state: str
    assessment: AssessmentOut


class DecisionOut(BaseModel):
    decision_id: str
    case_id: str
    type: str
    outcome: str
    reason_code: str
    rule_version: int
    actor: str
    created_at: str


class DecideResponse(BaseModel):
    case_id: str
    state: str
    decision: DecisionOut
    account_number: str | None


class AdvanceResponse(BaseModel):
    case_id: str
    state: str
    steps_run: list[str]
    decision: DecisionOut | None


class NotificationOut(BaseModel):
    notification_id: str
    case_id: str
    event: str
    template: str
    text: str
    details: dict[str, Any]
    created_at: str


class NotificationListOut(BaseModel):
    case_id: str
    notifications: list[NotificationOut]


def upload_out(view: DocumentView) -> UploadResponse:
    return UploadResponse(
        document_id=view.document_id,
        checklist_item=view.checklist_item,
        version=view.version,
        doc_class=view.doc_class,
        status=view.status,
        reason_code=view.reason_code,
        confidence_bp=view.confidence_bp,
        rule_version=view.rule_version,
    )


def document_list_out(case_id: str, views: list[DocumentView]) -> DocumentListOut:
    return DocumentListOut(
        case_id=case_id, documents=[DocumentViewOut(**asdict(view)) for view in views]
    )


def reject_out(rejection: DocumentRejection) -> RejectResponse:
    return RejectResponse(
        document_id=rejection.document_id, status="REJECTED", reason_code=rejection.reason_code
    )


def submit_out(result: SubmitResult) -> SubmitOut:
    return SubmitOut(
        case_id=result.case_id, state=result.state, missing_items=list(result.missing_items)
    )


def screening_out(result: ScreeningResult) -> ScreeningOut:
    return ScreeningOut(
        id=result.result_id,
        case_id=result.case_id,
        hits=[HitOut(**hit) for hit in result.hits],
        requires_manual_review=result.requires_manual_review,
        watchlist_version=result.watchlist_version,
        screened_at=result.screened_at,
    )


def assessment_out(assessment: RiskAssessment) -> AssessmentOut:
    return AssessmentOut(
        assessment_id=assessment.assessment_id,
        case_id=assessment.case_id,
        score=assessment.score,
        band=assessment.band,
        rule_version=assessment.rule_version,
        source=assessment.source,
        breakdown=[FactorOut(**asdict(item)) for item in assessment.breakdown],
        created_at=assessment.created_at,
    )


def decision_out(decision: Decision) -> DecisionOut:
    return DecisionOut(type="AUTO", **asdict(decision))


def decide_out(result: DecisionResult) -> DecideResponse:
    return DecideResponse(
        case_id=result.case_id,
        state=result.state,
        decision=decision_out(result.decision),
        account_number=result.account_number,
    )


def advance_out(result: AdvanceResult) -> AdvanceResponse:
    return AdvanceResponse(
        case_id=result.case_id,
        state=result.state,
        steps_run=list(result.steps_run),
        decision=None if result.decision is None else decision_out(result.decision),
    )


def notification_list_out(case_id: str, items: list[Notification]) -> NotificationListOut:
    return NotificationListOut(
        case_id=case_id,
        notifications=[NotificationOut(**_without_contact(asdict(item))) for item in items],
    )


def _without_contact(data: dict[str, Any]) -> dict[str, Any]:
    data.pop("contact_masked", None)
    return data
