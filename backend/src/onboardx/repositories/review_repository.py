"""Overrides (append-only, one per case) and the manual-review queue query (AC-08, NFR-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import Override
from onboardx.domain.enums import CaseState
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.cases import CaseModel, StateHistoryModel
from onboardx.repositories.models.pipeline import DecisionModel
from onboardx.repositories.models.review import OverrideModel

PREVIOUS_STATE = str(CaseState.MANUAL_REVIEW)


def _to_override(row: OverrideModel) -> Override:
    return Override(
        override_id=row.override_id,
        case_id=row.case_id,
        actor=row.actor,
        decision=row.decision,
        reason_code=row.reason_code,
        comment=row.comment,
        rule_version=row.rule_version,
        created_at=row.created_at,
    )


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_override(self, override: Override) -> None:
        self._session.add(
            OverrideModel(
                override_id=override.override_id,
                case_id=override.case_id,
                actor=override.actor,
                previous_state=PREVIOUS_STATE,
                decision=override.decision,
                reason_code=override.reason_code,
                comment=override.comment,
                rule_version=override.rule_version,
                created_at=override.created_at,
            )
        )
        flush_unique(self._session)

    def override_for_case(self, case_id: str) -> Override | None:
        row = self._session.scalars(
            select(OverrideModel).where(OverrideModel.case_id == case_id)
        ).first()
        return None if row is None else _to_override(row)

    def queue(
        self, *, product: str | None, reason_code: str | None
    ) -> list[tuple[str, str, str, str]]:
        """(case_id, product, reason_code, entered_review_at) of MANUAL_REVIEW cases, oldest
        first; no name or contact column is selected."""
        query = (
            select(CaseModel.case_id, CaseModel.product, DecisionModel.reason_code)
            .add_columns(StateHistoryModel.created_at)
            .join(DecisionModel, DecisionModel.case_id == CaseModel.case_id)
            .join(
                StateHistoryModel,
                (StateHistoryModel.case_id == CaseModel.case_id)
                & (StateHistoryModel.to_state == PREVIOUS_STATE),
            )
            .where(CaseModel.state == PREVIOUS_STATE)
        )
        if product is not None:
            query = query.where(CaseModel.product == product)
        if reason_code is not None:
            query = query.where(DecisionModel.reason_code == reason_code)
        rows = self._session.execute(
            query.order_by(StateHistoryModel.created_at, StateHistoryModel.seq)
        ).all()
        return [(str(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows]
