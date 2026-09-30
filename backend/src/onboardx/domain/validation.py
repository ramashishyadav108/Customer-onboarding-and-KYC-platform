"""Input validation for leads and profiles (lead-capture spec). Pure; raises ValidationError."""

import re
from datetime import date

from onboardx.domain.enums import OccupationCategory, Product
from onboardx.domain.errors import ValidationError

_PHONE = re.compile(r"^[0-9]{10}$")
_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_TWO_UPPER = re.compile(r"^[A-Z]{2}$")
NAME_MAX = 100
EMAIL_MAX = 254
HOME_COUNTRY = "IN"


def valid_contact(contact: str) -> bool:
    """10-digit phone number or a syntactically valid email address."""
    return bool(_PHONE.match(contact)) or (
        len(contact) <= EMAIL_MAX and bool(_EMAIL.match(contact))
    )


def validate_lead(
    name: str | None, contact: str | None, product: str | None
) -> list[tuple[str, str]]:
    """Return field-level problems for a lead; empty when valid."""
    problems: list[tuple[str, str]] = []
    if name is None or not name.strip():
        problems.append(("name", "name is required"))
    elif len(name) > NAME_MAX:
        problems.append(("name", f"name must be at most {NAME_MAX} characters"))
    if contact is None or not contact.strip():
        problems.append(("contact", "contact is required"))
    elif not valid_contact(contact):
        problems.append(("contact", "contact must be a 10-digit phone number or a valid email"))
    if product not in {p.value for p in Product}:
        problems.append(("product", "product must be one of Savings, Current, NRE"))
    return problems


def validate_profile(
    *,
    date_of_birth: date,
    annual_income: int,
    occupation_category: str,
    country_code: str,
    state_code: str | None,
    today: date,
) -> list[tuple[str, str]]:
    """Return field-level problems for profile fields; empty when valid (AC-01, DD-14)."""
    problems: list[tuple[str, str]] = []
    if date_of_birth >= today:
        problems.append(("date_of_birth", "date_of_birth must be in the past"))
    if type(annual_income) is not int or annual_income < 0:
        problems.append(("annual_income", "annual_income must be a non-negative integer"))
    if occupation_category not in {o.value for o in OccupationCategory}:
        problems.append(("occupation_category", "unknown occupation_category"))
    if not _TWO_UPPER.match(country_code):
        problems.append(("country_code", "country_code must be two uppercase letters"))
    elif country_code == HOME_COUNTRY and state_code is None:
        problems.append(("state_code", "state_code is required when country_code is IN"))
    if state_code is not None and not _TWO_UPPER.match(state_code):
        problems.append(("state_code", "state_code must be two uppercase letters"))
    elif state_code is not None and country_code != HOME_COUNTRY:
        problems.append(("state_code", "state_code must be omitted unless country_code is IN"))
    return problems


def ensure_valid(problems: list[tuple[str, str]]) -> None:
    if problems:
        raise ValidationError(problems)
