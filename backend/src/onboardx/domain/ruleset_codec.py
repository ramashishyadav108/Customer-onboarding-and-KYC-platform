"""Conversion between RuleSet and its JSON shape (api-contracts RuleSet; integers only)."""

from typing import Any

from onboardx.domain.enums import RuleSetStatus
from onboardx.domain.errors import ValidationError
from onboardx.domain.risk import AgeBand, IncomeBand, RuleSet


def ruleset_to_dict(rule_set: RuleSet) -> dict[str, Any]:
    return {
        "version": rule_set.version,
        "status": str(rule_set.status),
        "weights": dict(rule_set.weights),
        "points": {
            "age": [
                {
                    "label": b.label,
                    "min_years": b.min_years,
                    "max_years": b.max_years,
                    "points": b.points,
                }
                for b in rule_set.age_bands
            ],
            "income_band": [
                {"code": b.code, "min_inr": b.min_inr, "max_inr": b.max_inr, "points": b.points}
                for b in rule_set.income_bands
            ],
            "occupation_category": dict(rule_set.occupation_points),
            "geography": dict(rule_set.geography_points),
        },
        "geography_map": dict(rule_set.geography_map),
        "geography_default": rule_set.geography_default,
        "border_states": list(rule_set.border_states),
        "thresholds": {"low_max": rule_set.low_max, "medium_max": rule_set.medium_max},
        "author": rule_set.author,
        "created_at": rule_set.created_at,
        "published_at": rule_set.published_at,
    }


def ruleset_from_dict(data: dict[str, Any]) -> RuleSet:
    """Build a RuleSet; malformed shapes raise ValidationError, never KeyError."""
    try:
        points = data["points"]
        return RuleSet(
            version=data["version"],
            status=RuleSetStatus(data["status"]),
            weights=dict(data["weights"]),
            age_bands=tuple(AgeBand(**band) for band in points["age"]),
            income_bands=tuple(IncomeBand(**band) for band in points["income_band"]),
            occupation_points=dict(points["occupation_category"]),
            geography_points=dict(points["geography"]),
            geography_map=dict(data["geography_map"]),
            geography_default=data["geography_default"],
            border_states=tuple(data["border_states"]),
            low_max=data["thresholds"]["low_max"],
            medium_max=data["thresholds"]["medium_max"],
            author=data["author"],
            created_at=data["created_at"],
            published_at=data.get("published_at"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError.single("rule_set", "malformed rule set") from error
