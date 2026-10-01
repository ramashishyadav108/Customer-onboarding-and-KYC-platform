"""Read models for the compliance review panel and the approved-case account (AC-07, AC-08)."""

from onboardx.domain.enums import CaseState
from onboardx.domain.errors import NotFoundError
from onboardx.domain.masking import mask_account_number
from onboardx.domain.views import AccountView, EvidenceView
from onboardx.repositories.unit_of_work import UnitOfWorkFactory


class EvidenceService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def get_evidence(self, case_id: str) -> EvidenceView:
        """Screening hits, latest risk assessment, documents, decision, override and history."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            decision = uow.decisions.get_for_case(case_id)
            account = uow.accounts.get_for_case(case_id)
            in_review = decision is not None and decision.outcome == str(CaseState.MANUAL_REVIEW)
            return EvidenceView(
                case_id=case_id,
                state=str(case.state),
                product=str(case.product),
                documents=tuple(uow.documents.list_views(case_id, include_superseded=True)),
                screening=uow.screenings.latest_result(case_id),
                risk_assessment=uow.assessments.latest(case_id),
                decision=decision,
                override=uow.review.override_for_case(case_id),
                review_reason_code=decision.reason_code if decision and in_review else None,
                account_number_masked=(
                    None if account is None else mask_account_number(account.account_number)
                ),
                history=tuple(uow.state_history.list_for_case(case_id)),
            )

    def get_account(self, case_id: str) -> AccountView:
        """The stub account of an APPROVED case; 404 while none exists."""
        with self._uow_factory() as uow:
            if uow.cases.get(case_id) is None:
                raise NotFoundError("case")
            account = uow.accounts.get_for_case(case_id)
            if account is None:
                raise NotFoundError("account")
            return AccountView(
                case_id, str(account.product), account.account_number, account.created_at
            )
