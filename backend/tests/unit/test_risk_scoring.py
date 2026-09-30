"""AC-06 / NFR-01: integer-only risk scoring, bands, branches and worked examples."""

import random
from datetime import date

import pytest

from onboardx.domain.enums import RiskBand
from onboardx.domain.errors import ValidationError
from onboardx.domain.risk import (
    ProfileInputs,
    RuleSet,
    age_in_years,
    band_for_score,
    geography_category,
    score_profile,
)
from onboardx.domain.ruleset_codec import ruleset_from_dict
from ruleset_fixture import V1_DICT

ON = date(2026, 10, 1)
V1 = ruleset_from_dict(V1_DICT)


def dob_for_age(years: int) -> date:
    return date(ON.year - years, 1, 1)


def profile(
    age: int = 35,
    income: int = 3_000_000,
    occupation: str = "SELF_EMPLOYED",
    country: str = "IN",
    state: str | None = "MH",
) -> ProfileInputs:
    return ProfileInputs(dob_for_age(age), income, occupation, country, state)


def factor(result_profile: ProfileInputs, name: str, rule_set: RuleSet = V1) -> tuple[str, int]:
    item = next(
        f for f in score_profile(result_profile, rule_set, ON).breakdown if f.factor == name
    )
    return item.value_label, item.points


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("inputs", "score", "band"),
    [
        (profile(35, 3_000_000, "SELF_EMPLOYED", "IN", "MH"), 16, RiskBand.LOW),
        (profile(65, 12_000_000, "BUSINESS_OWNER", "GB", None), 45, RiskBand.MEDIUM),
        (profile(65, 12_000_000, "CASH_INTENSIVE", "KP", None), 72, RiskBand.HIGH),
    ],
    ids=["example-16-LOW", "example-45-MEDIUM", "example-72-HIGH"],
)
def test_ac06_7_worked_examples(inputs: ProfileInputs, score: int, band: RiskBand) -> None:
    """AC-06.7: the three worked examples score 16 LOW, 45 MEDIUM, 72 HIGH."""
    result = score_profile(inputs, V1, ON)
    assert (result.score, result.band) == (score, band)
    assert result.rule_version == 1


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, RiskBand.LOW),
        (29, RiskBand.LOW),
        (30, RiskBand.MEDIUM),
        (59, RiskBand.MEDIUM),
        (60, RiskBand.HIGH),
        (100, RiskBand.HIGH),
    ],
)
def test_ac06_7_band_boundaries(score: int, band: RiskBand) -> None:
    """AC-06.7: boundaries 29 LOW, 30 MEDIUM, 59 MEDIUM, 60 HIGH."""
    assert band_for_score(score, 29, 59) is band


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize("score", [-1, 101])
def test_ac06_8_band_rejects_out_of_range_scores(score: int) -> None:
    """AC-06.8: scores outside 0..100 are rejected."""
    with pytest.raises(ValidationError):
        band_for_score(score, 29, 59)


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("age", "label", "points"),
    [(0, "under 18", 100), (17, "under 18", 100), (18, "18-24", 30), (24, "18-24", 30),
     (25, "25-60", 0), (60, "25-60", 0), (61, "61+", 40), (90, "61+", 40)],
)  # fmt: skip
def test_ac06_age_factor_branches(age: int, label: str, points: int) -> None:
    """AC-06: every age band and both edges of each band."""
    assert factor(profile(age=age), "age") == (label, points)


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("income", "code", "points"),
    [(0, "B1", 10), (499_999, "B1", 10), (500_000, "B2", 0), (2_499_999, "B2", 0),
     (2_500_000, "B3", 30), (9_999_999, "B3", 30), (10_000_000, "B4", 60),
     (999_999_999, "B4", 60)],
)  # fmt: skip
def test_ac06_income_band_branches(income: int, code: str, points: int) -> None:
    """AC-06: every income band boundary."""
    assert factor(profile(income=income), "income_band") == (code, points)


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("occupation", "points"),
    [("SALARIED", 0), ("RETIRED", 10), ("STUDENT", 10), ("SELF_EMPLOYED", 30),
     ("BUSINESS_OWNER", 50), ("CASH_INTENSIVE", 80)],
)  # fmt: skip
def test_ac06_occupation_branches(occupation: str, points: int) -> None:
    """AC-06: all six occupation categories; label never echoes the raw occupation."""
    label, got = factor(profile(occupation=occupation), "occupation_category")
    assert got == points
    assert occupation not in label


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("country", "state", "category", "points"),
    [
        ("IN", "MH", "DOMESTIC", 0),
        ("IN", "JK", "DOMESTIC_BORDER", 40),
        ("IN", "PB", "DOMESTIC_BORDER", 40),
        ("IN", "AS", "DOMESTIC_BORDER", 40),
        ("GB", None, "FOREIGN_STANDARD", 30),
        ("KP", None, "FOREIGN_HIGH_RISK", 100),
        ("IR", None, "FOREIGN_HIGH_RISK", 100),
        ("ZZ", None, "FOREIGN_STANDARD", 30),
    ],
)
def test_ac06_geography_branches_including_border_state(
    country: str, state: str | None, category: str, points: int
) -> None:
    """AC-06 / DD-14: IN + JK/PB/AS is DOMESTIC_BORDER; other states and countries per map."""
    assert geography_category(country, state, V1) == category
    assert factor(profile(country=country, state=state), "geography") == (category, points)


@pytest.mark.ac("AC-06")
def test_ac06_border_state_does_not_apply_outside_india() -> None:
    """AC-06: a border state code with a non-IN country stays on the country map."""
    assert geography_category("GB", "PB", V1) == "FOREIGN_STANDARD"


@pytest.mark.ac("AC-06")
def test_ac06_border_state_changes_the_score() -> None:
    """AC-06: age 35, B3, SELF_EMPLOYED in PB: 750 + 900 + 1000 = 2650 -> 26 LOW."""
    plain = score_profile(profile(state="MH"), V1, ON)
    border = score_profile(profile(state="PB"), V1, ON)
    assert (plain.score, border.score) == (16, 26)
    assert border.band is RiskBand.LOW


@pytest.mark.ac("AC-06")
def test_ac06_9_breakdown_contribution_is_points_times_weight() -> None:
    """AC-06.9: per-factor breakdown; score is the integer sum // 100."""
    result = score_profile(profile(65, 12_000_000, "CASH_INTENSIVE", "KP", None), V1, ON)
    assert [f.factor for f in result.breakdown] == [
        "age", "income_band", "occupation_category", "geography",
    ]  # fmt: skip
    assert [f.contribution for f in result.breakdown] == [800, 1500, 2400, 2500]
    assert all(f.contribution == f.points * f.weight for f in result.breakdown)
    assert result.score == sum(f.contribution for f in result.breakdown) // 100 == 72


@pytest.mark.ac("AC-06")
def test_ac06_maximum_profile_scores_84_high() -> None:
    """AC-06: worst-case inputs under v1 give 100*20+60*25+80*30+100*25 = 8400 -> 84."""
    result = score_profile(profile(10, 99_000_000, "CASH_INTENSIVE", "KP", None), V1, ON)
    assert (result.score, result.band) == (84, RiskBand.HIGH)


@pytest.mark.ac("AC-06")
def test_ac06_score_is_deterministic() -> None:
    """AC-06 (risk-classifier): classification is deterministic for a fixed rule version."""
    inputs = profile(44, 7_000_000, "BUSINESS_OWNER", "US", None)
    assert score_profile(inputs, V1, ON) == score_profile(inputs, V1, ON)


@pytest.mark.ac("AC-06")
def test_ac06_8_score_is_an_int_in_range_for_1000_profiles() -> None:
    """AC-06.8: property test over 1,000 seeded random profiles."""
    rng = random.Random(20261001)  # noqa: S311 - seeded test data, not security
    occupations = ["SALARIED", "RETIRED", "STUDENT", "SELF_EMPLOYED", "BUSINESS_OWNER",
                   "CASH_INTENSIVE"]  # fmt: skip
    countries = ["IN", "GB", "US", "AE", "KP", "IR", "FR", "JP"]
    for _ in range(1000):
        country = rng.choice(countries)
        state = rng.choice(["JK", "PB", "AS", "MH", "KA"]) if country == "IN" else None
        inputs = profile(
            rng.randint(0, 100), rng.randint(0, 50_000_000), rng.choice(occupations), country, state
        )
        result = score_profile(inputs, V1, ON)
        assert type(result.score) is int
        assert 0 <= result.score <= 100
        assert result.band is band_for_score(result.score, V1.low_max, V1.medium_max)


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("dob", "years"),
    [(date(2000, 10, 1), 26), (date(2000, 10, 2), 25), (date(2000, 12, 31), 25),
     (date(2026, 10, 1), 0), (date(2000, 2, 29), 26)],
)  # fmt: skip
def test_ac06_age_in_years_is_birthday_aware(dob: date, years: int) -> None:
    """AC-06: age is whole years at the evaluation date."""
    assert age_in_years(dob, ON) == years


@pytest.mark.ac("AC-06")
def test_ac06_future_date_of_birth_is_rejected() -> None:
    """AC-06: a date of birth after the evaluation date has no age band."""
    with pytest.raises(ValidationError):
        score_profile(ProfileInputs(date(2030, 1, 1), 1, "SALARIED", "IN", "MH"), V1, ON)


@pytest.mark.ac("AC-06")
def test_ac06_unknown_occupation_is_rejected() -> None:
    """AC-06: an unknown occupation category is a ValidationError."""
    with pytest.raises(ValidationError):
        score_profile(profile(occupation="ASTRONAUT"), V1, ON)
