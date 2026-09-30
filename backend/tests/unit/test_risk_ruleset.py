"""AC-06 / NFR-01: RuleSet integer-only validation and publish-validity rules."""

from decimal import Decimal
from typing import Any

import pytest

from onboardx.domain.enums import RuleSetStatus
from onboardx.domain.errors import ValidationError
from onboardx.domain.risk import AgeBand, IncomeBand, publish_problems
from onboardx.domain.ruleset_codec import ruleset_from_dict, ruleset_to_dict
from ruleset_fixture import V1_DICT, v1_copy


@pytest.mark.ac("AC-06")
def test_ac06_1_ruleset_has_version_status_weights_points_thresholds() -> None:
    """AC-06.1: int version, status, integer weights, points, bands and thresholds."""
    rule_set = ruleset_from_dict(v1_copy())
    assert rule_set.version == 1
    assert rule_set.status is RuleSetStatus.PUBLISHED
    assert dict(rule_set.weights) == {
        "age": 20, "income_band": 25, "occupation_category": 30, "geography": 25,
    }  # fmt: skip
    assert len(rule_set.age_bands) == 4 and len(rule_set.income_bands) == 4
    assert (rule_set.low_max, rule_set.medium_max) == (29, 59)
    assert rule_set.border_states == ("JK", "PB", "AS")


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize("bad", [0.25, Decimal("0.25"), True, "20", None, 20.0])
def test_ac06_2_weights_reject_non_integers(bad: Any) -> None:
    """AC-06.2: a float, Decimal, bool or string weight raises ValidationError."""
    data = v1_copy()
    data["weights"]["age"] = bad
    with pytest.raises(ValidationError):
        ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize("bad", [0.5, Decimal("10.5"), "10"])
def test_ac06_2_points_reject_non_integers(bad: Any) -> None:
    """AC-06.2: points tables reject non-integers in every factor table."""
    for mutate in (
        lambda d: d["points"]["occupation_category"].__setitem__("SALARIED", bad),
        lambda d: d["points"]["geography"].__setitem__("DOMESTIC", bad),
        lambda d: d["points"]["age"][0].__setitem__("points", bad),
        lambda d: d["points"]["income_band"][0].__setitem__("points", bad),
    ):
        data = v1_copy()
        mutate(data)
        with pytest.raises(ValidationError):
            ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize("field", ["low_max", "medium_max"])
def test_ac06_2_thresholds_reject_floats(field: str) -> None:
    """AC-06.2: thresholds reject a float such as 29.5."""
    data = v1_copy()
    data["thresholds"][field] = 29.5
    with pytest.raises(ValidationError):
        ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
def test_ac06_2_band_boundaries_reject_floats() -> None:
    """AC-06.2: income and age band boundaries are integers too."""
    with pytest.raises(ValidationError):
        IncomeBand("B1", 0, 499999.5, 10)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        AgeBand("x", 1.5, None, 10)  # type: ignore[arg-type]


@pytest.mark.ac("AC-06")
def test_ac06_points_outside_0_100_are_rejected() -> None:
    """AC-06: factor points must be integers 0..100."""
    data = v1_copy()
    data["points"]["geography"]["DOMESTIC"] = 101
    with pytest.raises(ValidationError):
        ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
def test_ac06_weights_must_define_the_four_factors() -> None:
    """AC-06: weights with a missing or extra factor are malformed."""
    data = v1_copy()
    del data["weights"]["geography"]
    with pytest.raises(ValidationError):
        ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
def test_ac06_malformed_dict_raises_validation_error_not_keyerror() -> None:
    """AC-06: a missing section surfaces as ValidationError."""
    data = v1_copy()
    del data["points"]
    with pytest.raises(ValidationError):
        ruleset_from_dict(data)


@pytest.mark.ac("AC-06")
def test_ac06_5_valid_v1_has_no_publish_problems() -> None:
    """AC-06.5: weights sum 100 and thresholds 29 < 59 < 100 are publishable."""
    assert publish_problems(ruleset_from_dict(v1_copy())) == []


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("weights_age", "low", "medium", "reasons"),
    [
        (21, 29, 59, ["WEIGHTS_SUM"]),
        (19, 29, 59, ["WEIGHTS_SUM"]),
        (20, 59, 59, ["THRESHOLDS_ORDER"]),
        (20, 60, 59, ["THRESHOLDS_ORDER"]),
        (20, 29, 100, ["THRESHOLDS_ORDER"]),
        (20, -1, 59, ["THRESHOLDS_ORDER"]),
        (25, 70, 50, ["WEIGHTS_SUM", "THRESHOLDS_ORDER"]),
    ],
)
def test_ac06_5_publish_problems(
    weights_age: int, low: int, medium: int, reasons: list[str]
) -> None:
    """AC-06.5: RULESET_INVALID reasons for weights sum and strictly ascending thresholds."""
    data = v1_copy()
    data["weights"]["age"] = weights_age
    data["thresholds"] = {"low_max": low, "medium_max": medium}
    assert publish_problems(ruleset_from_dict(data)) == reasons


@pytest.mark.ac("AC-06")
def test_ac06_codec_round_trip_matches_spec_v1() -> None:
    """AC-06.6: the codec round-trips the spec v1 values unchanged."""
    assert ruleset_to_dict(ruleset_from_dict(v1_copy())) == V1_DICT
