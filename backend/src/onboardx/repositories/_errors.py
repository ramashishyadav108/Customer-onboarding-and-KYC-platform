"""Translation of database trigger failures into domain errors."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from onboardx.domain.enums import CaseState
from onboardx.domain.errors import CaseLockedError, PublishedRuleSetImmutableError
from onboardx.repositories.models.cases import CaseModel

LOCKED_CASE_MESSAGE = "case is locked"
LOCKED_PROFILE_MESSAGE = "profile is locked"
IMMUTABLE_RULESET_MESSAGE = "published rule set is immutable"


def is_trigger_error(error: IntegrityError, message: str) -> bool:
    return message in str(error.orig)


def case_locked(session: Session, case_id: str) -> CaseLockedError:
    row = session.get(CaseModel, case_id)
    state = CaseState(row.state) if row is not None else CaseState.APPROVED
    return CaseLockedError(case_id, state)


def ruleset_immutable(version: int) -> PublishedRuleSetImmutableError:
    return PublishedRuleSetImmutableError(version)
