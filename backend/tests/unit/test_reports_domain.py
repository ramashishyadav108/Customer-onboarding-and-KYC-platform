"""AC-10 / NFR-01: integer-only report arithmetic and override reason lists."""

from datetime import date

import pytest

from onboardx.domain.enums import (
    OVERRIDE_REASONS_BY_DECISION,
    OverrideDecision,
    OverrideReason,
    Product,
    ReclassifyReason,
)
from onboardx.domain.errors import ValidationError
from onboardx.domain.reports import (
    ReportFilters,
    age_minutes,
    bucket_counts,
    build_auto_approval,
    build_backlog,
    build_funnel,
    floor_avg,
    ratio_bp,
)


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(
    ("total", "count", "expected"), [(0, 0, 0), (10, 3, 3), (21, 2, 10), (-1, 0, 0), (7, 7, 1)]
)
def test_ac10_floor_avg_is_integer_floor_and_zero_when_empty(
    total: int, count: int, expected: int
) -> None:
    """E5-S1 AC5: floor division; an empty set averages to zero."""
    assert floor_avg(total, count) == expected


@pytest.mark.ac("AC-10")
@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize(
    ("n", "d", "expected"), [(1, 3, 3333), (2, 3, 6666), (0, 5, 0), (5, 5, 10000), (3, 0, 0)]
)
def test_ac10_ratio_bp_floors_and_handles_empty_denominator(n: int, d: int, expected: int) -> None:
    """Basis points are floored integers."""
    assert ratio_bp(n, d) == expected and isinstance(ratio_bp(n, d), int)


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(
    ("ages", "counts"),
    [([], [0, 0, 0]), ([0, 59], [2, 0, 0]), ([60, 1440], [0, 2, 0]), ([1441, 9999], [0, 0, 2])],
)
def test_ac10_4_bucket_boundaries(ages: list[int], counts: list[int]) -> None:
    """AC-10.4: under 60, 60 to 1440 inclusive, over 1440."""
    assert [b.count for b in bucket_counts(ages)] == counts


@pytest.mark.ac("AC-10")
def test_ac10_4_backlog_oldest_and_count() -> None:
    """Backlog: count and oldest age; empty is zero."""
    backlog = build_backlog([5, 300, 70])
    assert (backlog.count, backlog.oldest_age_minutes) == (3, 300)
    assert build_backlog([]).oldest_age_minutes == 0


@pytest.mark.ac("AC-10")
def test_ac10_3_funnel_with_no_data_is_all_zero() -> None:
    """AC-10.7: empty funnel has zero counts and zero conversion."""
    assert all(s.count == 0 and s.conversion_bp == 0 for s in build_funnel({}))


@pytest.mark.ac("AC-10")
def test_ac10_3_funnel_conversion_chain() -> None:
    """Chain stages convert from the previous stage, outcomes from CLASSIFIED."""
    stages = build_funnel(
        {"INITIATED": 4, "DOCS_SUBMITTED": 2, "SCREENED": 2, "CLASSIFIED": 2, "APPROVED": 1}
    )
    assert [s.conversion_bp for s in stages] == [10000, 5000, 10000, 10000, 0, 5000, 0]


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(
    ("approved", "decided", "rate", "met"),
    [(0, 0, 0, False), (59, 100, 5900, False), (60, 100, 6000, True), (100, 100, 10000, True)],
)
def test_ac10_6_auto_approval_met_flag(approved: int, decided: int, rate: int, met: bool) -> None:
    """AC-10.6: met when rate_bp >= the 6000 target."""
    result = build_auto_approval(approved, decided)
    assert (result.rate_bp, result.target_bp, result.met) == (rate, 6000, met)


@pytest.mark.ac("AC-10")
def test_ac10_age_minutes_never_negative() -> None:
    """Ages are whole minutes and clamp at zero."""
    assert age_minutes(1000, 1000 - 119) == 1 and age_minutes(10, 500) == 0


@pytest.mark.ac("AC-10")
def test_ac10_7_filters_reject_an_inverted_range() -> None:
    """from after to is a validation error naming 'from'."""
    with pytest.raises(ValidationError) as info:
        ReportFilters(Product.NRE, date(2026, 9, 5), date(2026, 9, 1))
    assert info.value.fields[0][0] == "from"
    assert ReportFilters(None, date(2026, 9, 1), date(2026, 9, 1)).product is None


@pytest.mark.ac("AC-08")
def test_ac08_2_reason_lists_match_the_contract() -> None:
    """DD-3: three approve codes, four reject codes, seven in total; DD-4 reclassify codes."""
    approve = OVERRIDE_REASONS_BY_DECISION[OverrideDecision.APPROVE]
    reject = OVERRIDE_REASONS_BY_DECISION[OverrideDecision.REJECT]
    assert len(approve) == 3 and len(reject) == 4
    assert set(approve) | set(reject) == set(OverrideReason) and not set(approve) & set(reject)
    assert [str(c) for c in ReclassifyReason] == [
        "NEW_INFORMATION", "SCORING_ERROR", "MANUAL_ASSESSMENT",
    ]  # fmt: skip
