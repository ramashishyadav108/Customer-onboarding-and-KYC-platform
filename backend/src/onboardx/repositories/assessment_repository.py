"""Risk assessments: append-only; the current assessment is the highest seq (AC-06.9)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import RiskAssessment
from onboardx.domain.risk import FactorScore
from onboardx.repositories.models.pipeline import RiskAssessmentModel


def _to_assessment(row: RiskAssessmentModel) -> RiskAssessment:
    return RiskAssessment(
        assessment_id=row.assessment_id,
        case_id=row.case_id,
        score=row.score,
        band=row.band,
        rule_version=row.rule_version,
        source=row.source,
        breakdown=tuple(FactorScore(**item) for item in row.breakdown),
        created_at=row.created_at,
    )


class AssessmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, assessment: RiskAssessment) -> None:
        self._session.add(
            RiskAssessmentModel(
                assessment_id=assessment.assessment_id,
                case_id=assessment.case_id,
                score=assessment.score,
                band=assessment.band,
                rule_version=assessment.rule_version,
                source=assessment.source,
                breakdown=[
                    {
                        "factor": f.factor,
                        "value_label": f.value_label,
                        "points": f.points,
                        "weight": f.weight,
                        "contribution": f.contribution,
                    }
                    for f in assessment.breakdown
                ],
                created_at=assessment.created_at,
            )
        )
        self._session.flush()

    def latest(self, case_id: str) -> RiskAssessment | None:
        row = self._session.scalars(
            select(RiskAssessmentModel)
            .where(RiskAssessmentModel.case_id == case_id)
            .order_by(RiskAssessmentModel.seq.desc())
            .limit(1)
        ).first()
        return None if row is None else _to_assessment(row)

    def list_for_case(self, case_id: str) -> list[RiskAssessment]:
        rows = self._session.scalars(
            select(RiskAssessmentModel)
            .where(RiskAssessmentModel.case_id == case_id)
            .order_by(RiskAssessmentModel.seq)
        ).all()
        return [_to_assessment(row) for row in rows]
