"""Decision rules (AC-07): auto-approve only a clean LOW case, else MANUAL_REVIEW with a reason.

Precedence of review reasons: AML_HIT, PEP_HIT, DOC_UNRECOGNISED, RISK_MEDIUM, RISK_HIGH.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from onboardx.domain.enums import (
    CaseState,
    DecisionReason,
    DocStatus,
    RiskBand,
    ScreeningReasonCode,
)


@dataclass(frozen=True)
class DecisionOutcome:
    outcome: CaseState
    reason: DecisionReason


def _screening_reason(hits: Iterable[Mapping[str, str]]) -> DecisionReason | None:
    codes = {hit["reason_code"] for hit in hits}
    if str(ScreeningReasonCode.AML_HIT) in codes:
        return DecisionReason.AML_HIT
    if str(ScreeningReasonCode.PEP_HIT) in codes:
        return DecisionReason.PEP_HIT
    return None


def _review_reason(
    band: RiskBand, hits: Iterable[Mapping[str, str]], document_statuses: Iterable[str]
) -> DecisionReason | None:
    reason = _screening_reason(hits)
    if reason is not None:
        return reason
    if any(status != str(DocStatus.VERIFIED) for status in document_statuses):
        return DecisionReason.DOC_UNRECOGNISED
    if band is RiskBand.MEDIUM:
        return DecisionReason.RISK_MEDIUM
    if band is RiskBand.HIGH:
        return DecisionReason.RISK_HIGH
    return None


def decide(
    band: RiskBand,
    hits: Iterable[Mapping[str, str]],
    document_statuses: Iterable[str],
    *,
    manual_policy: bool = False,
) -> DecisionOutcome:
    """APPROVED/AUTO_APPROVED only if LOW, no hit and every current document VERIFIED.

    With ``manual_policy`` a clean case is routed to a compliance officer (MANUAL_POLICY) instead;
    every specific review reason keeps its precedence (AC-15).
    """
    review = _review_reason(band, hits, document_statuses)
    if review is None and manual_policy:
        review = DecisionReason.MANUAL_POLICY
    if review is None:
        return DecisionOutcome(CaseState.APPROVED, DecisionReason.AUTO_APPROVED)
    return DecisionOutcome(CaseState.MANUAL_REVIEW, review)
