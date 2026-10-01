"""The v1 rule set as a plain dict, written independently of the migration (spec values)."""

from copy import deepcopy
from typing import Any

V1_DICT: dict[str, Any] = {
    "version": 1,
    "status": "PUBLISHED",
    "weights": {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25},
    "points": {
        "age": [
            {"label": "under 18", "min_years": 0, "max_years": 17, "points": 100},
            {"label": "18-24", "min_years": 18, "max_years": 24, "points": 30},
            {"label": "25-60", "min_years": 25, "max_years": 60, "points": 0},
            {"label": "61+", "min_years": 61, "max_years": None, "points": 40},
        ],
        "income_band": [
            {"code": "B1", "min_inr": 0, "max_inr": 499999, "points": 10},
            {"code": "B2", "min_inr": 500000, "max_inr": 2499999, "points": 0},
            {"code": "B3", "min_inr": 2500000, "max_inr": 9999999, "points": 30},
            {"code": "B4", "min_inr": 10000000, "max_inr": None, "points": 60},
        ],
        "occupation_category": {
            "SALARIED": 0,
            "RETIRED": 10,
            "STUDENT": 10,
            "SELF_EMPLOYED": 30,
            "BUSINESS_OWNER": 50,
            "CASH_INTENSIVE": 80,
        },
        "geography": {
            "DOMESTIC": 0,
            "FOREIGN_STANDARD": 30,
            "DOMESTIC_BORDER": 40,
            "FOREIGN_HIGH_RISK": 100,
        },
    },
    "geography_map": {
        "IN": "DOMESTIC",
        "GB": "FOREIGN_STANDARD",
        "US": "FOREIGN_STANDARD",
        "AE": "FOREIGN_STANDARD",
        "KP": "FOREIGN_HIGH_RISK",
        "IR": "FOREIGN_HIGH_RISK",
    },
    "geography_default": "FOREIGN_STANDARD",
    "border_states": ["JK", "PB", "AS"],
    "thresholds": {"low_max": 29, "medium_max": 59},
    "author": "system",
    "created_at": "2026-10-01T00:00:00Z",
    "published_at": "2026-10-01T00:00:00Z",
}


def v1_copy() -> dict[str, Any]:
    return deepcopy(V1_DICT)
