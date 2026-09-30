"""NFR-03 masking, account-number derivation and AC-05 name-matching helpers."""

import hashlib
import re

import pytest

from onboardx.domain.account_numbers import derive_account_number
from onboardx.domain.enums import Product
from onboardx.domain.masking import mask_account_number, mask_contact
from onboardx.domain.matching import matches, normalise_name, token_key


@pytest.mark.nfr("NFR-03")
@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("contact", "masked"),
    [
        ("9999999921", "********21"),
        ("test.person@example.com", "*" * 21 + "om"),
        ("ab", "**"),
        ("a", "*"),
        ("abc", "*bc"),
    ],
)
def test_nfr03_mask_contact_keeps_only_last_two_characters(contact: str, masked: str) -> None:
    """NFR-03 / AC-01.4: only the last 2 characters of contact are visible."""
    assert mask_contact(contact) == masked
    assert len(mask_contact(contact)) == len(contact)


@pytest.mark.nfr("NFR-03")
def test_nfr03_mask_account_number_keeps_prefix_and_last_four() -> None:
    """NFR-03: SAV123456789012 -> SAV********9012."""
    assert mask_account_number("SAV123456789012") == "SAV********9012"
    assert mask_account_number("NRE12") == "*****"


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(
    ("product", "prefix"),
    [(Product.SAVINGS, "SAV"), (Product.CURRENT, "CUR"), (Product.NRE, "NRE")],
)
def test_ac07_account_number_format_and_derivation(product: Product, prefix: str) -> None:
    """AC-07: prefix by product plus 12 digits from int(sha256(case_id)) % 10**12."""
    case_id = "3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10"
    number = derive_account_number(case_id, product)
    assert re.fullmatch(rf"{prefix}[0-9]{{12}}", number)
    expected = int(hashlib.sha256(case_id.encode()).hexdigest(), 16) % 10**12
    assert number == f"{prefix}{expected:012d}"


@pytest.mark.ac("AC-07")
def test_ac07_account_number_is_deterministic_and_case_specific() -> None:
    """AC-07: same case gives the same number; different cases differ."""
    a = derive_account_number("case-a", Product.SAVINGS)
    assert a == derive_account_number("case-a", Product.SAVINGS)
    assert a != derive_account_number("case-b", Product.SAVINGS)


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize(
    "variant",
    ["Test Person One", "test person one", "TEST, PERSON ONE", "One Test Person",
     "  Test   Person\tOne ", "Test-Person.One", "Ｔest Ｐerson Ｏne"],
)  # fmt: skip
def test_ac05_2_variants_of_a_watchlist_name_match(variant: str) -> None:
    """AC-05.2: case, punctuation, spacing, token order and NFKC variants match."""
    assert matches(variant, ["Test Person One"])


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("other", ["Test Person Two", "Test Person", "Person One Test Extra", ""])
def test_ac05_2_unrelated_names_do_not_match(other: str) -> None:
    """AC-05.2: no fuzzy matching; different token sets do not hit."""
    assert not matches(other, ["Test Person One"])


@pytest.mark.ac("AC-05")
def test_ac05_matches_any_alias() -> None:
    """AC-05: a case matches when its tokens equal any alias of the entry."""
    assert not matches("p. one", ["Sample Name", "T P One"])
    assert matches("one p t", ["Sample Name", "T P One"])


@pytest.mark.ac("AC-05")
def test_ac05_normalise_name_returns_sorted_lowercase_tokens() -> None:
    """AC-05: normalisation sorts tokens after NFKC, lowercase and punctuation strip."""
    assert normalise_name("Zed, Alpha  Beta") == ["alpha", "beta", "zed"]
    assert token_key("Zed, Alpha  Beta") == "alpha beta zed"
    assert normalise_name("!!!") == []
