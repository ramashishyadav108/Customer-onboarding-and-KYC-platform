"""Decisions (one per case) and accounts (one per case): append-only (NFR-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import Account, Decision
from onboardx.domain.enums import Product
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.pipeline import AccountModel, DecisionModel


def _to_decision(row: DecisionModel) -> Decision:
    return Decision(
        decision_id=row.decision_id,
        case_id=row.case_id,
        outcome=row.outcome,
        reason_code=row.reason_code,
        rule_version=row.rule_version,
        actor=row.actor,
        created_at=row.created_at,
    )


def _to_account(row: AccountModel) -> Account:
    return Account(
        account_id=row.account_id,
        case_id=row.case_id,
        product=Product(row.product),
        account_number=row.account_number,
        created_at=row.created_at,
    )


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, decision: Decision) -> None:
        self._session.add(
            DecisionModel(
                decision_id=decision.decision_id,
                case_id=decision.case_id,
                type="AUTO",
                outcome=decision.outcome,
                reason_code=decision.reason_code,
                rule_version=decision.rule_version,
                actor=decision.actor,
                created_at=decision.created_at,
            )
        )
        flush_unique(self._session)

    def get_for_case(self, case_id: str) -> Decision | None:
        row = self._session.scalars(
            select(DecisionModel).where(DecisionModel.case_id == case_id)
        ).first()
        return None if row is None else _to_decision(row)


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, account: Account) -> None:
        self._session.add(
            AccountModel(
                account_id=account.account_id,
                case_id=account.case_id,
                product=str(account.product),
                account_number=account.account_number,
                created_at=account.created_at,
            )
        )
        flush_unique(self._session)

    def get_for_case(self, case_id: str) -> Account | None:
        row = self._session.scalars(
            select(AccountModel).where(AccountModel.case_id == case_id)
        ).first()
        return None if row is None else _to_account(row)
