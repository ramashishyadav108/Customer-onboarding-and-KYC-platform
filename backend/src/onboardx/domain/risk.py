"""Risk rule sets and fixed-point scoring (AC-06, NFR-01).

Integers only: ``score = sum(points * weight) // 100``. No true division anywhere; numeric
inputs are checked with an exact-type test so non-integer numbers are rejected.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from onboardx.domain.enums import GeographyCategory, RiskBand, RuleSetStatus
from onboardx.domain.errors import ValidationError

FACTORS = ("age", "income_band", "occupation_category", "geography")
MAX_SCORE = 100
WEIGHT_TOTAL = 100
HOME_COUNTRY = "IN"


def require_int(value: object, field: str) -> int:
    """Return value when it is exactly an int (bool, float and Decimal are rejected)."""
    if type(value) is not int:
        raise ValidationError.single(field, "must be an integer")
    return value


def _require_points(value: object, field: str) -> int:
    points = require_int(value, field)
    if not 0 <= points <= MAX_SCORE:
        raise ValidationError.single(field, "points must be between 0 and 100")
    return points


@dataclass(frozen=True)
class AgeBand:
    label: str
    min_years: int
    max_years: int | None
    points: int

    def __post_init__(self) -> None:
        require_int(self.min_years, "points.age.min_years")
        if self.max_years is not None:
            require_int(self.max_years, "points.age.max_years")
        _require_points(self.points, "points.age.points")

    def contains(self, years: int) -> bool:
        return years >= self.min_years and (self.max_years is None or years <= self.max_years)


@dataclass(frozen=True)
class IncomeBand:
    code: str
    min_inr: int
    max_inr: int | None
    points: int

    def __post_init__(self) -> None:
        require_int(self.min_inr, "points.income_band.min_inr")
        if self.max_inr is not None:
            require_int(self.max_inr, "points.income_band.max_inr")
        _require_points(self.points, "points.income_band.points")

    def contains(self, income: int) -> bool:
        return income >= self.min_inr and (self.max_inr is None or income <= self.max_inr)


@dataclass(frozen=True)
class RuleSet:
    """A versioned rule set; mutable only while DRAFT (enforced by service and DB trigger)."""

    version: int
    status: RuleSetStatus
    weights: Mapping[str, int]
    age_bands: tuple[AgeBand, ...]
    income_bands: tuple[IncomeBand, ...]
    occupation_points: Mapping[str, int]
    geography_points: Mapping[str, int]
    geography_map: Mapping[str, str]
    geography_default: str
    border_states: tuple[str, ...]
    low_max: int
    medium_max: int
    author: str
    created_at: str
    published_at: str | None = None

    def __post_init__(self) -> None:
        require_int(self.version, "version")
        require_int(self.low_max, "thresholds.low_max")
        require_int(self.medium_max, "thresholds.medium_max")
        if set(self.weights) != set(FACTORS):
            raise ValidationError.single("weights", "weights must define exactly the four factors")
        for factor, weight in self.weights.items():
            require_int(weight, f"weights.{factor}")
        for name, table in (
            ("occupation_category", self.occupation_points),
            ("geography", self.geography_points),
        ):
            for key, value in table.items():
                _require_points(value, f"points.{name}.{key}")

    @property
    def is_published(self) -> bool:
        return self.status is RuleSetStatus.PUBLISHED


def publish_problems(rule_set: RuleSet) -> list[str]:
    """Reasons a rule set cannot be published: WEIGHTS_SUM, THRESHOLDS_ORDER (AC-06.5)."""
    reasons: list[str] = []
    if sum(rule_set.weights.values()) != WEIGHT_TOTAL:
        reasons.append("WEIGHTS_SUM")
    if not 0 <= rule_set.low_max < rule_set.medium_max < MAX_SCORE:
        reasons.append("THRESHOLDS_ORDER")
    return reasons


def band_for_score(score: int, low_max: int, medium_max: int) -> RiskBand:
    """LOW up to low_max, MEDIUM up to medium_max, HIGH above (v1: 29 / 59)."""
    if not 0 <= score <= MAX_SCORE:
        raise ValidationError.single("score", "score must be between 0 and 100")
    if score <= low_max:
        return RiskBand.LOW
    if score <= medium_max:
        return RiskBand.MEDIUM
    return RiskBand.HIGH


@dataclass(frozen=True)
class ProfileInputs:
    date_of_birth: date
    annual_income: int
    occupation_category: str
    country_code: str
    state_code: str | None


@dataclass(frozen=True)
class FactorScore:
    factor: str
    value_label: str
    points: int
    weight: int
    contribution: int


@dataclass(frozen=True)
class ScoreResult:
    score: int
    band: RiskBand
    rule_version: int
    breakdown: tuple[FactorScore, ...]


def age_in_years(date_of_birth: date, on: date) -> int:
    """Whole years between date_of_birth and ``on`` (birthday-aware, integer only)."""
    before_birthday = (on.month, on.day) < (date_of_birth.month, date_of_birth.day)
    return on.year - date_of_birth.year - (1 if before_birthday else 0)


def geography_category(country_code: str, state_code: str | None, rule_set: RuleSet) -> str:
    """DOMESTIC_BORDER for IN plus a border state; otherwise the static country map."""
    if country_code == HOME_COUNTRY and state_code in rule_set.border_states:
        return GeographyCategory.DOMESTIC_BORDER.value
    return rule_set.geography_map.get(country_code, rule_set.geography_default)


def _factor(name: str, label: str, points: int, weight: int) -> FactorScore:
    return FactorScore(name, label, points, weight, points * weight)


def _age_factor(inputs: ProfileInputs, rule_set: RuleSet, on: date) -> FactorScore:
    years = age_in_years(inputs.date_of_birth, on)
    for band in rule_set.age_bands:
        if years >= 0 and band.contains(years):
            return _factor("age", band.label, band.points, rule_set.weights["age"])
    raise ValidationError.single("date_of_birth", "no age band covers this date of birth")


def _income_factor(inputs: ProfileInputs, rule_set: RuleSet) -> FactorScore:
    for band in rule_set.income_bands:
        if band.contains(inputs.annual_income):
            return _factor("income_band", band.code, band.points, rule_set.weights["income_band"])
    raise ValidationError.single("annual_income", "no income band covers this income")


def _occupation_factor(inputs: ProfileInputs, rule_set: RuleSet) -> FactorScore:
    points = rule_set.occupation_points.get(inputs.occupation_category)
    if points is None:
        raise ValidationError.single("occupation_category", "unknown occupation_category")
    weight = rule_set.weights["occupation_category"]
    return _factor("occupation_category", f"tier-{points}", points, weight)


def _geography_factor(inputs: ProfileInputs, rule_set: RuleSet) -> FactorScore:
    category = geography_category(inputs.country_code, inputs.state_code, rule_set)
    points = rule_set.geography_points.get(category)
    if points is None:
        raise ValidationError.single("country_code", "no points defined for geography category")
    return _factor("geography", category, points, rule_set.weights["geography"])


def score_profile(inputs: ProfileInputs, rule_set: RuleSet, on: date) -> ScoreResult:
    """Deterministic integer score and band for a profile under one rule set version."""
    breakdown = (
        _age_factor(inputs, rule_set, on),
        _income_factor(inputs, rule_set),
        _occupation_factor(inputs, rule_set),
        _geography_factor(inputs, rule_set),
    )
    total = sum(item.contribution for item in breakdown)
    score = max(0, min(MAX_SCORE, total // 100))
    band = band_for_score(score, rule_set.low_max, rule_set.medium_max)
    return ScoreResult(score, band, rule_set.version, breakdown)
