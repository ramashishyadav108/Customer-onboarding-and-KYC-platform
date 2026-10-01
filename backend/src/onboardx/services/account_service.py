"""Stubbed account creation for APPROVED cases (AC-07). No network, no real account."""

import uuid

from onboardx.domain.account_numbers import derive_account_number
from onboardx.domain.entities import Account
from onboardx.domain.enums import AuditEvent, CaseState
from onboardx.domain.errors import InvalidOnboardingStateException, NotFoundError
from onboardx.domain.masking import mask_account_number
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork
from onboardx.services.audit_service import AuditService


class AccountService:
    def __init__(self, clock: Clock, audit: AuditService) -> None:
        self._clock = clock
        self._audit = audit

    def create_account(self, uow: UnitOfWork, *, case_id: str, actor: str, role: str) -> Account:
        """Create (once) the account of an APPROVED case; writes nothing otherwise."""
        case = uow.cases.get(case_id)
        if case is None:
            raise NotFoundError("case")
        if case.state is not CaseState.APPROVED:
            raise InvalidOnboardingStateException(case_id, case.state, CaseState.APPROVED)
        existing = uow.accounts.get_for_case(case_id)
        if existing is not None:
            return existing
        account = Account(
            str(uuid.uuid4()),
            case_id,
            case.product,
            derive_account_number(case_id, case.product),
            to_iso_z(self._clock.now()),
        )
        uow.accounts.add(account)
        self._audit.record(
            uow,
            event=AuditEvent.ACCOUNT_CREATED,
            actor=actor,
            role=role,
            case_id=case_id,
            payload={
                "account_number_masked": mask_account_number(account.account_number),
                "product": str(case.product),
            },
        )
        return account
