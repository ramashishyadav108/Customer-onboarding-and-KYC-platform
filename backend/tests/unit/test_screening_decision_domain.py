"""E3-S1 / AC-05 screening matches and E4-S1 / AC-07 decision logic (every branch)."""

import pytest

from onboardx.domain.decision import decide
from onboardx.domain.entities import WatchlistEntry
from onboardx.domain.enums import CaseState, DecisionReason, NotificationEvent, RiskBand
from onboardx.domain.matching import token_key
from onboardx.domain.notifications import render_text, template_name
from onboardx.domain.screening import entry_matches, screen_name


def entry(entry_id: str, name: str, aliases: list[str], list_type: str) -> WatchlistEntry:
    return WatchlistEntry(
        entry_id,
        name,
        tuple(aliases),
        list_type,
        token_key(name),
        tuple(token_key(a) for a in aliases),
    )


ENTRIES = [
    entry("e1", "Test Person One", ["T P One"], "AML"),
    entry("e2", "Mock Minister Epsilon", [], "PEP"),
    entry("e3", "Example Senator Zeta", ["Senator Zeta"], "PEP"),
]


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize(
    "name",
    [
        "Test Person One",
        "test person one",
        "TEST PERSON ONE",
        "Test  Person-One",
        "PERSON ONE TEST",
        "  Test   Person   One  ",
        "Test, Person. One!",
        "one person test",
    ],
)
def test_ac05_2_variants_of_a_listed_name_hit(name: str) -> None:
    """AC-05.2: case, punctuation, spacing and token order do not defeat the match."""
    outcome = screen_name(name, ENTRIES)
    assert [h["entry_id"] for h in outcome.hits] == ["e1"]


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("name", ["T P One", "t.p. one", "ONE T P"])
def test_ac05_2_aliases_hit_too(name: str) -> None:
    """AC-05.2: an alias token key also matches."""
    assert [h["entry_id"] for h in screen_name(name, ENTRIES).hits] == ["e1"]


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize(
    "name",
    ["Test Person Two", "Test Person", "Test Person One Two", "Alpha Beta", "Tes Person One", ""],
)
def test_ac05_2_near_misses_and_unrelated_names_do_not_hit(name: str) -> None:
    """AC-05.2 / v1: exact token equality only; no fuzzy matching, empty names never match."""
    outcome = screen_name(name, ENTRIES)
    assert outcome.hits == () and outcome.requires_manual_review is False


@pytest.mark.ac("AC-05")
def test_ac05_3_aml_and_pep_hits_carry_their_reason_codes() -> None:
    """AC-05.3: AML entries give AML_HIT, PEP entries give PEP_HIT, with entry id and list."""
    (aml,) = screen_name("Test Person One", ENTRIES).hits
    (pep,) = screen_name("Mock Minister Epsilon", ENTRIES).hits
    assert aml == {"entry_id": "e1", "list_type": "AML", "reason_code": "AML_HIT"}
    assert pep == {"entry_id": "e2", "list_type": "PEP", "reason_code": "PEP_HIT"}


@pytest.mark.ac("AC-05")
def test_ac05_3_a_hit_sets_requires_manual_review() -> None:
    assert screen_name("Senator Zeta", ENTRIES).requires_manual_review is True


@pytest.mark.ac("AC-05")
def test_ac05_5_a_clean_name_has_an_empty_hit_list() -> None:
    outcome = screen_name("Test Person Alpha", ENTRIES)
    assert outcome.hits == () and not outcome.requires_manual_review


@pytest.mark.ac("AC-05")
def test_ac05_every_matching_entry_is_reported() -> None:
    """Two entries with the same key both appear (one hit per entry)."""
    twins = [*ENTRIES, entry("e9", "Person One Test", [], "PEP")]
    assert [h["entry_id"] for h in screen_name("Test Person One", twins).hits] == ["e1", "e9"]


@pytest.mark.ac("AC-05")
def test_ac05_entry_with_empty_alias_key_never_matches_an_empty_name() -> None:
    blank = WatchlistEntry("e0", "", (), "AML", "", ("",))
    assert entry_matches("", blank) is False


@pytest.mark.ac("AC-05")
def test_ac05_unicode_normalisation_applies() -> None:
    """NFKC: full-width letters match their ASCII listing."""
    assert screen_name("Ｔｅｓｔ Ｐｅｒｓｏｎ Ｏｎｅ", ENTRIES).hits != ()


CLEAN = ["VERIFIED", "VERIFIED", "VERIFIED"]
AML = [{"entry_id": "e1", "list_type": "AML", "reason_code": "AML_HIT"}]
PEP = [{"entry_id": "e2", "list_type": "PEP", "reason_code": "PEP_HIT"}]


@pytest.mark.ac("AC-07")
def test_ac07_1_clean_low_case_is_auto_approved() -> None:
    """AC-07.1: LOW, no hit, all VERIFIED -> APPROVED with AUTO_APPROVED."""
    result = decide(RiskBand.LOW, [], CLEAN)
    assert (result.outcome, result.reason) == (CaseState.APPROVED, DecisionReason.AUTO_APPROVED)


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(
    ("band", "hits", "docs", "reason"),
    [
        (RiskBand.LOW, AML, CLEAN, DecisionReason.AML_HIT),
        (RiskBand.LOW, PEP, CLEAN, DecisionReason.PEP_HIT),
        (RiskBand.LOW, [], ["VERIFIED", "FLAGGED"], DecisionReason.DOC_UNRECOGNISED),
        (RiskBand.LOW, [], ["REJECTED"], DecisionReason.DOC_UNRECOGNISED),
        (RiskBand.MEDIUM, [], CLEAN, DecisionReason.RISK_MEDIUM),
        (RiskBand.HIGH, [], CLEAN, DecisionReason.RISK_HIGH),
    ],
)
def test_ac07_2_each_review_branch_gives_its_reason(
    band: RiskBand, hits: list[dict[str, str]], docs: list[str], reason: DecisionReason
) -> None:
    """AC-07.2: every non-approval branch routes to MANUAL_REVIEW with the right code."""
    result = decide(band, hits, docs)
    assert (result.outcome, result.reason) == (CaseState.MANUAL_REVIEW, reason)


@pytest.mark.ac("AC-07")
def test_ac07_2_precedence_aml_then_pep_then_docs_then_risk() -> None:
    """AC-07.2: AML_HIT > PEP_HIT > DOC_UNRECOGNISED > RISK_MEDIUM > RISK_HIGH."""
    assert decide(RiskBand.HIGH, AML + PEP, ["FLAGGED"]).reason is DecisionReason.AML_HIT
    assert decide(RiskBand.HIGH, PEP, ["FLAGGED"]).reason is DecisionReason.PEP_HIT
    assert decide(RiskBand.HIGH, [], ["FLAGGED"]).reason is DecisionReason.DOC_UNRECOGNISED
    assert decide(RiskBand.MEDIUM, [], CLEAN).reason is DecisionReason.RISK_MEDIUM
    assert decide(RiskBand.HIGH, [], CLEAN).reason is DecisionReason.RISK_HIGH


@pytest.mark.ac("AC-05")
def test_ac05_4_a_case_with_a_hit_is_never_auto_approved() -> None:
    """AC-05.4: whatever the band and documents, a hit cannot be approved automatically."""
    for band in RiskBand:
        assert decide(band, AML, CLEAN).outcome is CaseState.MANUAL_REVIEW


@pytest.mark.ac("AC-07")
def test_ac07_no_documents_at_all_does_not_block_a_clean_low_case() -> None:
    """With no current documents there is nothing unverified (submission gates that)."""
    assert decide(RiskBand.LOW, [], []).outcome is CaseState.APPROVED


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize("event", list(NotificationEvent))
def test_ac09_every_event_renders_text_without_contact_or_reason_leaks(
    event: NotificationEvent,
) -> None:
    """AC-09.5: text is generic; no contact, no AML/PEP wording."""
    text = render_text(event, product="Savings", item_code="ID_PROOF", reason_code="DOC_OTHER")
    assert text and "@" not in text and "AML" not in text and "PEP" not in text
    assert template_name(event).startswith("notification.")
