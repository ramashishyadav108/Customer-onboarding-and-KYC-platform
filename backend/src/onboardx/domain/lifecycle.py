"""Onboarding lifecycle: the frozen transition table (AC-04) and terminal-state rule (NFR-08).

INITIATED -> DOCS_SUBMITTED -> SCREENED -> CLASSIFIED -> {APPROVED | REJECTED | MANUAL_REVIEW},
MANUAL_REVIEW -> {APPROVED | REJECTED}. APPROVED and REJECTED have no exits.
"""

from collections.abc import Mapping
from types import MappingProxyType

from onboardx.domain.enums import CaseState
from onboardx.domain.errors import InvalidOnboardingStateException

_S = CaseState

ALLOWED_TRANSITIONS: Mapping[CaseState, frozenset[CaseState]] = MappingProxyType(
    {
        _S.INITIATED: frozenset({_S.DOCS_SUBMITTED}),
        _S.DOCS_SUBMITTED: frozenset({_S.SCREENED}),
        _S.SCREENED: frozenset({_S.CLASSIFIED}),
        _S.CLASSIFIED: frozenset({_S.APPROVED, _S.REJECTED, _S.MANUAL_REVIEW}),
        _S.MANUAL_REVIEW: frozenset({_S.APPROVED, _S.REJECTED}),
        _S.APPROVED: frozenset(),
        _S.REJECTED: frozenset(),
    }
)


def is_terminal(state: CaseState) -> bool:
    """APPROVED and REJECTED are terminal: no transition leaves them."""
    return not ALLOWED_TRANSITIONS[state]


def can_transition(from_state: CaseState, to_state: CaseState) -> bool:
    return to_state in ALLOWED_TRANSITIONS[from_state]


def assert_transition(case_id: str, from_state: CaseState, to_state: CaseState) -> None:
    """Raise InvalidOnboardingStateException unless from_state -> to_state is in the table."""
    if not can_transition(from_state, to_state):
        raise InvalidOnboardingStateException(case_id, from_state, to_state)
