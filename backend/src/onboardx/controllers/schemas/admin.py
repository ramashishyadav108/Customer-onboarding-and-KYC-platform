"""Rule-set request schemas: StrictInt for every numeric field so fractions are a 422."""

from pydantic import BaseModel, StrictInt


class AgeBandIn(BaseModel):
    label: str
    min_years: StrictInt
    max_years: StrictInt | None
    points: StrictInt


class IncomeBandIn(BaseModel):
    code: str
    min_inr: StrictInt
    max_inr: StrictInt | None
    points: StrictInt


class PointsIn(BaseModel):
    age: list[AgeBandIn]
    income_band: list[IncomeBandIn]
    occupation_category: dict[str, StrictInt]
    geography: dict[str, StrictInt]


class ThresholdsIn(BaseModel):
    low_max: StrictInt
    medium_max: StrictInt


class RuleSetUpdate(BaseModel):
    weights: dict[str, StrictInt] | None = None
    points: PointsIn | None = None
    geography_map: dict[str, str] | None = None
    geography_default: str | None = None
    thresholds: ThresholdsIn | None = None
    border_states: list[str] | None = None
