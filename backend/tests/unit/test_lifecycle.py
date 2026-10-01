"""AC-04 / E1-S4 AC1, AC4 / NFR-08: the lifecycle transition table (full from/to matrix)."""

from itertools import product

import pytest

from onboardx.domain.enums import CaseState
from onboardx.domain.errors import InvalidOnboardingStateException
from onboardx.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    assert_transition,
    can_transition,
    is_terminal,
)

S = CaseState
# Independent copy of the eight edges listed in E1-S4 AC1.
EXPECTED_EDGES = {
    (S.INITIATED, S.DOCS_SUBMITTED),
    (S.DOCS_SUBMITTED, S.SCREENED),
    (S.SCREENED, S.CLASSIFIED),
    (S.CLASSIFIED, S.APPROVED),
    (S.CLASSIFIED, S.REJECTED),
    (S.CLASSIFIED, S.MANUAL_REVIEW),
    (S.MANUAL_REVIEW, S.APPROVED),
    (S.MANUAL_REVIEW, S.REJECTED),
}
MATRIX = list(product(CaseState, CaseState))


@pytest.mark.ac("AC-04")
@pytest.mark.parametrize(("source", "target"), MATRIX, ids=[f"{a}->{b}" for a, b in MATRIX])
@pytest.mark.ac("AC-04.1")
@pytest.mark.ac("AC-04.2")
def test_ac04_full_transition_matrix(source: CaseState, target: CaseState) -> None:
    """AC-04: exactly the eight specified edges are allowed; all other pairs raise."""
    if (source, target) in EXPECTED_EDGES:
        assert_transition("case-1", source, target)
        assert can_transition(source, target)
    else:
        assert not can_transition(source, target)
        with pytest.raises(InvalidOnboardingStateException):
            assert_transition("case-1", source, target)


@pytest.mark.ac("AC-04")
def test_ac04_table_has_exactly_eight_edges() -> None:
    """AC-04: the table contains exactly the eight edges and no others."""
    edges = {(a, b) for a, targets in ALLOWED_TRANSITIONS.items() for b in targets}
    assert edges == EXPECTED_EDGES
    assert len(MATRIX) == 49


@pytest.mark.ac("AC-04")
def test_ac04_exception_carries_case_and_states() -> None:
    """AC-04 (E1-S4 AC2): the exception carries case_id, from_state, to_state and code."""
    with pytest.raises(InvalidOnboardingStateException) as info:
        assert_transition("c-9", S.INITIATED, S.APPROVED)
    error = info.value
    assert (error.case_id, error.from_state, error.to_state) == ("c-9", S.INITIATED, S.APPROVED)
    assert error.code == "INVALID_STATE"
    assert error.details == {
        "case_id": "c-9",
        "from_state": "INITIATED",
        "to_state": "APPROVED",
    }


@pytest.mark.ac("AC-04")
@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize("terminal", [S.APPROVED, S.REJECTED])
def test_nfr08_terminal_states_have_no_exits(terminal: CaseState) -> None:
    """NFR-08 / AC-04.4: APPROVED and REJECTED are terminal; every exit raises."""
    assert is_terminal(terminal)
    for target in CaseState:
        with pytest.raises(InvalidOnboardingStateException):
            assert_transition("c", terminal, target)


@pytest.mark.ac("AC-04")
@pytest.mark.parametrize(
    "state", [S.INITIATED, S.DOCS_SUBMITTED, S.SCREENED, S.CLASSIFIED, S.MANUAL_REVIEW]
)
def test_ac04_non_terminal_states_have_exits(state: CaseState) -> None:
    """AC-04: only APPROVED and REJECTED are terminal."""
    assert not is_terminal(state)


@pytest.mark.ac("AC-04")
def test_ac04_transition_table_is_frozen() -> None:
    """AC-04: the table is an immutable mapping of frozensets."""
    with pytest.raises(TypeError):
        ALLOWED_TRANSITIONS[S.INITIATED] = frozenset()  # type: ignore[index]
    assert all(isinstance(v, frozenset) for v in ALLOWED_TRANSITIONS.values())
    assert set(ALLOWED_TRANSITIONS) == set(CaseState)
