"""AC-01 input validation rules and NFR-04 password hashing."""

from datetime import date

import pytest

from onboardx.domain.errors import ValidationError
from onboardx.domain.validation import ensure_valid, valid_contact, validate_lead, validate_profile
from onboardx.services.passwords import hash_password, verify_password

TODAY = date(2026, 10, 1)


def profile_problems(**overrides: object) -> list[tuple[str, str]]:
    values: dict[str, object] = {
        "date_of_birth": date(1990, 4, 12),
        "annual_income": 3_000_000,
        "occupation_category": "SELF_EMPLOYED",
        "country_code": "IN",
        "state_code": "MH",
        "today": TODAY,
    }
    values.update(overrides)
    return validate_profile(**values)  # type: ignore[arg-type]


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("contact", "ok"),
    [
        ("9999999921", True),
        ("test.person@example.com", True),
        ("a+b@sub.example.org", True),
        ("99999", False),
        ("99999999999", False),
        ("99999abcde", False),
        ("not-an-email", False),
        ("a@b", False),
        ("@example.com", False),
    ],
)
def test_ac01_2_contact_validation(contact: str, ok: bool) -> None:
    """AC-01.2: contact is a 10-digit phone or a valid email."""
    assert valid_contact(contact) is ok


@pytest.mark.ac("AC-01")
def test_ac01_2_lead_validation_lists_every_bad_field() -> None:
    """AC-01.2: missing name/contact and bad product produce a field-level list."""
    problems = validate_lead(None, "x", "Gold")
    assert [field for field, _ in problems] == ["name", "contact", "product"]
    assert validate_lead("Test Person", "9999999921", "NRE") == []
    assert validate_lead("x" * 101, "9999999921", "NRE")[0][0] == "name"
    assert validate_lead("   ", "9999999921", "NRE")[0][0] == "name"


@pytest.mark.ac("AC-01")
def test_ac01_ensure_valid_raises_validation_error_with_fields() -> None:
    """AC-01.2: ensure_valid raises the domain ValidationError carrying fields."""
    with pytest.raises(ValidationError) as info:
        ensure_valid([("name", "required")])
    assert info.value.details == {"fields": [{"field": "name", "message": "required"}]}
    ensure_valid([])


@pytest.mark.ac("AC-01")
def test_ac01_5_valid_profile_has_no_problems() -> None:
    """AC-01.5: a complete profile validates."""
    assert profile_problems() == []
    assert profile_problems(country_code="GB", state_code=None) == []


@pytest.mark.ac("AC-01")
def test_ac01_state_code_required_when_country_is_india() -> None:
    """AC-01 / DD-14: state_code is required when country_code is IN."""
    assert [f for f, _ in profile_problems(state_code=None)] == ["state_code"]


@pytest.mark.ac("AC-01")
def test_ac01_state_code_must_be_omitted_outside_india() -> None:
    """AC-01 / DD-14: state_code is only for IN."""
    assert [f for f, _ in profile_problems(country_code="GB", state_code="PB")] == ["state_code"]


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("date_of_birth", date(2026, 10, 1)),
        ("date_of_birth", date(2030, 1, 1)),
        ("annual_income", -1),
        ("annual_income", 10.5),
        ("occupation_category", "ASTRONAUT"),
        ("country_code", "india"),
        ("country_code", "I"),
        ("state_code", "pb"),
    ],
)
def test_ac01_5_invalid_profile_fields(field: str, value: object) -> None:
    """AC-01.5: bad date, income, occupation, country or state code are reported by field."""
    assert field in [f for f, _ in profile_problems(**{field: value})]


@pytest.mark.nfr("NFR-04")
def test_nfr04_password_hash_is_salted_pbkdf2_and_verifies() -> None:
    """NFR-04 / E1-S2 AC2: salted PBKDF2-HMAC-SHA256; same password gives different hashes."""
    first = hash_password("demo-secret", iterations=1000)
    second = hash_password("demo-secret", iterations=1000)
    assert first.startswith("pbkdf2_sha256$1000$")
    assert first != second
    assert "demo-secret" not in first
    assert verify_password("demo-secret", first)
    assert not verify_password("demo-secreT", first)


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("stored", ["", "plain", "md5$1$aa$bb", "pbkdf2_sha256$x$aa$bb", "a$b$c"])
def test_nfr04_malformed_stored_hash_never_verifies(stored: str) -> None:
    """NFR-04: malformed stored hashes fail closed."""
    assert not verify_password("anything", stored)
