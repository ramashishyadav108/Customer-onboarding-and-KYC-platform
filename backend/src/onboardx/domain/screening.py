"""AML/PEP screening of an applicant name against watchlist entries (AC-05).

Exact equality of normalised, sorted token keys (see ``matching``); no fuzzy matching in v1.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from onboardx.domain.entities import WatchlistEntry
from onboardx.domain.enums import ListType, ScreeningReasonCode
from onboardx.domain.matching import token_key

_REASON_BY_LIST = {
    str(ListType.AML): str(ScreeningReasonCode.AML_HIT),
    str(ListType.PEP): str(ScreeningReasonCode.PEP_HIT),
}


@dataclass(frozen=True)
class ScreeningOutcome:
    hits: tuple[dict[str, str], ...]

    @property
    def requires_manual_review(self) -> bool:
        return bool(self.hits)


def entry_matches(key: str, entry: WatchlistEntry) -> bool:
    """True when the applicant token key equals the entry name key or any alias key."""
    return bool(key) and (key == entry.name_tokens or key in entry.alias_tokens)


def screen_name(name: str, entries: Iterable[WatchlistEntry]) -> ScreeningOutcome:
    """One hit per matching entry: entry_id, list_type and AML_HIT / PEP_HIT."""
    key = token_key(name)
    hits = tuple(
        {
            "entry_id": entry.entry_id,
            "list_type": entry.list_type,
            "reason_code": _REASON_BY_LIST[entry.list_type],
        }
        for entry in entries
        if entry_matches(key, entry)
    )
    return ScreeningOutcome(hits)
