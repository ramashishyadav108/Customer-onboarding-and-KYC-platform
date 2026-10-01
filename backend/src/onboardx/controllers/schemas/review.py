"""Review queue, evidence, override, reclassify and account schemas (api-contracts 2.4, 2.5)."""

from dataclasses import asdict

from pydantic import BaseModel, Field

from onboardx.controllers.schemas.pipeline import (
    AssessmentOut,
    DecisionOut,
    DocumentViewOut,
    ScreeningOut,
    assessment_out,
    decision_out,
    screening_out,
)
from onboardx.domain.entities import Override
from onboardx.domain.views import AccountView, EvidenceView, OverrideResult, ReviewQueueItem


class ReviewQueueItemOut(BaseModel):
    case_id: str
    product: str
    reason_code: str
    age_minutes: int
    entered_review_at: str


class ReviewQueueOut(BaseModel):
    items: list[ReviewQueueItemOut]
    total: int


class OverrideRequest(BaseModel):
    decision: str
    reason_code: str
    comment: str | None = Field(default=None, max_length=500)


class ReclassifyRequest(BaseModel):
    band: str
    reason_code: str
    comment: str | None = Field(default=None, max_length=500)


class OverrideOut(BaseModel):
    override_id: str
    case_id: str
    actor: str
    previous_state: str = "MANUAL_REVIEW"
    decision: str
    reason_code: str
    comment: str | None
    rule_version: int
    created_at: str


class OverrideResponse(BaseModel):
    case_id: str
    state: str
    override: OverrideOut
    account_number: str | None


class HistoryOut(BaseModel):
    from_state: str | None
    to_state: str
    actor: str
    reason_code: str | None
    created_at: str


class EvidenceOut(BaseModel):
    case_id: str
    state: str
    product: str
    documents: list[DocumentViewOut]
    screening: ScreeningOut | None
    risk_assessment: AssessmentOut | None
    decision: DecisionOut | None
    override: OverrideOut | None
    review_reason_code: str | None
    account_number_masked: str | None
    history: list[HistoryOut]


class AccountOut(BaseModel):
    case_id: str
    product: str
    account_number: str
    created_at: str


def queue_out(items: list[ReviewQueueItem]) -> ReviewQueueOut:
    return ReviewQueueOut(
        items=[ReviewQueueItemOut(**asdict(item)) for item in items], total=len(items)
    )


def override_view(override: Override) -> OverrideOut:
    return OverrideOut(**asdict(override))


def override_out(result: OverrideResult) -> OverrideResponse:
    return OverrideResponse(
        case_id=result.case_id,
        state=result.state,
        override=override_view(result.override),
        account_number=result.account_number,
    )


def evidence_out(view: EvidenceView) -> EvidenceOut:
    return EvidenceOut(
        case_id=view.case_id,
        state=view.state,
        product=view.product,
        documents=[DocumentViewOut(**asdict(doc)) for doc in view.documents],
        screening=None if view.screening is None else screening_out(view.screening),
        risk_assessment=(
            None if view.risk_assessment is None else assessment_out(view.risk_assessment)
        ),
        decision=None if view.decision is None else decision_out(view.decision),
        override=None if view.override is None else override_view(view.override),
        review_reason_code=view.review_reason_code,
        account_number_masked=view.account_number_masked,
        history=[
            HistoryOut(
                from_state=None if h.from_state is None else str(h.from_state),
                to_state=str(h.to_state),
                actor=h.actor,
                reason_code=h.reason_code,
                created_at=h.created_at,
            )
            for h in view.history
        ],
    )


def account_out(view: AccountView, *, masked: str | None) -> AccountOut:
    number = masked if masked is not None else view.account_number
    return AccountOut(
        case_id=view.case_id,
        product=view.product,
        account_number=number,
        created_at=view.created_at,
    )
