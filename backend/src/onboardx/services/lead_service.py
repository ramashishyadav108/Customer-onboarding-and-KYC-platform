"""Lead registration (AC-01) and profile upsert. No PII is logged or put in audit payloads."""

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date

from onboardx.domain.entities import Case, CaseProfile
from onboardx.domain.enums import AuditEvent, CaseState, Product, Role
from onboardx.domain.errors import (
    CaseExistsError,
    CaseLockedError,
    NotFoundError,
    ProfileLockedError,
    ValidationError,
)
from onboardx.domain.lifecycle import is_terminal
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.validation import ensure_valid, validate_lead, validate_profile
from onboardx.repositories.idempotency_repository import IdempotencyRecord
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.auth_service import ANONYMOUS_PREFIX, AuthService
from onboardx.services.onboarding_service import OnboardingService

logger = logging.getLogger("onboardx.leads")
LEADS_SCOPE = "leads"


@dataclass(frozen=True)
class LeadResult:
    case_id: str
    state: CaseState
    product: Product
    access_token: str
    expires_in: int
    created: bool


class LeadService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        onboarding: OnboardingService,
        audit: AuditService,
        auth: AuthService,
        fingerprint_key: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._onboarding = onboarding
        self._audit = audit
        self._auth = auth
        self._key = fingerprint_key.encode()

    def register(
        self,
        *,
        name: str,
        contact: str,
        product: str,
        idempotency_key: str | None = None,
        owner: str | None = None,
    ) -> LeadResult:
        """Create a case in INITIATED (idempotent per Idempotency-Key) and a prospect token.

        With ``owner`` (a prospect account's username) the case is linked to that account and the
        token is issued for the account (AC-14.3); without it the lead is anonymous as before.
        """
        ensure_valid(validate_lead(name, contact, product))
        fingerprint = self._fingerprint(name.strip(), contact, product)
        with self._uow_factory() as uow:
            replayed = self._replay(uow, idempotency_key, fingerprint)
            if replayed is not None:
                return self._result(replayed, created=False, owner=owner)
            account = self._owner_without_case(uow, owner)
            case = self._create_case(uow, name.strip(), contact, Product(product))
            self._record_creation(uow, case, idempotency_key, fingerprint)
            if account is not None:
                uow.users.set_case(account, case.case_id)
            uow.commit()
        logger.info("lead created case_id=%s", case.case_id)
        return self._result(case, created=True, owner=owner if account is not None else None)

    def _owner_without_case(self, uow: UnitOfWork, owner: str | None) -> str | None:
        """The owning account's id; 409 CASE_EXISTS when the account already has a case."""
        if owner is None:
            return None
        user = uow.users.get_by_username(owner)
        if user is None or not user.active or user.role is not Role.PROSPECT:
            return None
        if user.case_id is not None:
            raise CaseExistsError
        return user.user_id

    def update_profile(
        self,
        *,
        case_id: str,
        date_of_birth: date,
        annual_income: int,
        occupation_category: str,
        country_code: str,
        state_code: str | None,
        actor: str,
    ) -> CaseProfile:
        """Store the profile while INITIATED (AC-01.5); 409 afterwards, 422 on bad values."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            if is_terminal(case.state):
                raise CaseLockedError(case_id, case.state)
            if case.state is not CaseState.INITIATED:
                raise ProfileLockedError(case_id, case.state)
            profile = self._validated_profile(
                case_id, date_of_birth, annual_income, occupation_category, country_code, state_code
            )
            uow.profiles.upsert(profile)
            self._audit.record(
                uow,
                event=AuditEvent.PROFILE_UPDATED,
                actor=actor,
                role=str(Role.PROSPECT),
                case_id=case_id,
                payload={"fields": sorted(_PROFILE_FIELDS)},
            )
            uow.commit()
        return profile

    def _validated_profile(
        self,
        case_id: str,
        date_of_birth: date,
        annual_income: int,
        occupation_category: str,
        country_code: str,
        state_code: str | None,
    ) -> CaseProfile:
        now = self._clock.now()
        ensure_valid(
            validate_profile(
                date_of_birth=date_of_birth,
                annual_income=annual_income,
                occupation_category=occupation_category,
                country_code=country_code,
                state_code=state_code,
                today=now.date(),
            )
        )
        return CaseProfile(
            case_id,
            date_of_birth,
            annual_income,
            occupation_category,
            country_code,
            state_code,
            to_iso_z(now),
        )

    def _fingerprint(self, name: str, contact: str, product: str) -> str:
        body = json.dumps({"n": name, "c": contact, "p": product}, sort_keys=True).encode()
        return hmac.new(self._key, body, hashlib.sha256).hexdigest()

    def _replay(self, uow: UnitOfWork, key: str | None, fingerprint: str) -> Case | None:
        if key is None:
            return None
        record = uow.idempotency.get(LEADS_SCOPE, key)
        if record is None:
            return None
        if record.request_hash != fingerprint:
            raise ValidationError.single("Idempotency-Key", "key was used with a different payload")
        case = uow.cases.get(str(record.response["case_id"]))
        if case is None:
            raise NotFoundError("case")
        return case

    def _create_case(self, uow: UnitOfWork, name: str, contact: str, product: Product) -> Case:
        version = uow.checklists.latest_version(product)
        if version is None:
            raise NotFoundError("checklist")
        now = to_iso_z(self._clock.now())
        case = Case(
            str(uuid.uuid4()), name, contact, product, CaseState.INITIATED, version, now, now
        )
        uow.cases.add(case)
        return case

    def _record_creation(
        self, uow: UnitOfWork, case: Case, key: str | None, fingerprint: str
    ) -> None:
        actor = f"prospect:{case.case_id}"
        role = str(Role.PROSPECT)
        self._onboarding.start_case(uow, case_id=case.case_id, actor=actor, role=role)
        self._audit.record(
            uow,
            event=AuditEvent.LEAD_CREATED,
            actor=actor,
            role=role,
            case_id=case.case_id,
            payload={"product": str(case.product)},
        )
        if key is not None:
            uow.idempotency.add(
                IdempotencyRecord(
                    LEADS_SCOPE, key, fingerprint, {"case_id": case.case_id}, case.created_at
                )
            )

    def _result(self, case: Case, *, created: bool, owner: str | None = None) -> LeadResult:
        subject = owner or f"{ANONYMOUS_PREFIX}{case.case_id}"
        issued = self._auth.issue_token(subject, Role.PROSPECT, case.case_id)
        return LeadResult(
            case.case_id, case.state, case.product, issued.access_token, issued.expires_in, created
        )


_PROFILE_FIELDS = (
    "date_of_birth",
    "annual_income",
    "occupation_category",
    "country_code",
    "state_code",
)
