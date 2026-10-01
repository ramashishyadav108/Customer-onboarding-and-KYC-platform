"""Watchlist name matching helpers (specs/screening_spec.md): exact normalised-token equality."""

import re
import unicodedata
from collections.abc import Iterable

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalise_name(name: str) -> list[str]:
    """NFKC, lowercase, strip punctuation, collapse whitespace, split into sorted tokens."""
    text = unicodedata.normalize("NFKC", name).lower()
    text = _PUNCTUATION.sub(" ", text)
    return sorted(text.split())


def token_key(name: str) -> str:
    """Canonical comparison key: the sorted tokens joined by a single space."""
    return " ".join(normalise_name(name))


def matches(applicant_name: str, candidate_names: Iterable[str]) -> bool:
    """True when the applicant's token key equals the key of any candidate name or alias."""
    key = token_key(applicant_name)
    return bool(key) and any(key == token_key(candidate) for candidate in candidate_names)
