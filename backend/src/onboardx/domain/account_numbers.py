"""Deterministic account number derivation (data-models 3.15)."""

import hashlib

from onboardx.domain.enums import Product

PREFIXES = {Product.SAVINGS: "SAV", Product.CURRENT: "CUR", Product.NRE: "NRE"}
DIGITS = 12


def derive_account_number(case_id: str, product: Product) -> str:
    """Product prefix plus 12 digits from sha256(case_id) mod 10**12, zero padded."""
    digest = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16)
    return f"{PREFIXES[product]}{digest % 10**DIGITS:0{DIGITS}d}"
