"""E2-S3 / AC-03: the stub classifier decides by file-name prefix only."""

import pytest

from onboardx.domain.classifier import ClassificationRule, classify_filename, match_rule

RULES = [
    ClassificationRule("pan_", "PAN", "VERIFIED", 9500, 1),
    ClassificationRule("aadhaar_", "AADHAAR", "VERIFIED", 9500, 2),
    ClassificationRule("passport_", "PASSPORT", "VERIFIED", 9500, 3),
    ClassificationRule("utility-bill_", "UTILITY_BILL", "VERIFIED", 9500, 4),
    ClassificationRule("photograph_", "PHOTOGRAPH", "VERIFIED", 9500, 5),
    ClassificationRule("gst-certificate_", "GST_CERTIFICATE", "VERIFIED", 9500, 6),
    ClassificationRule("visa_", "VISA", "VERIFIED", 9500, 7),
]
ALL_CLASSES = [r.doc_class for r in RULES]


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("filename", "doc_class"),
    [
        ("pan_valid.pdf", "PAN"),
        ("aadhaar_valid.jpg", "AADHAAR"),
        ("passport_valid.png", "PASSPORT"),
        ("utility-bill_valid.pdf", "UTILITY_BILL"),
        ("photograph_1.jpg", "PHOTOGRAPH"),
        ("gst-certificate_2.pdf", "GST_CERTIFICATE"),
        ("visa_3.png", "VISA"),
    ],
)
def test_ac03_1_2_known_prefixes_classify_verified_with_9500_bp(
    filename: str, doc_class: str
) -> None:
    """AC-03.1/03.2: each fixture prefix gives its class, VERIFIED, 9500 bp, no reason."""
    result = classify_filename(filename, RULES, 1, ALL_CLASSES)
    assert (result.doc_class, result.status, result.confidence_bp) == (doc_class, "VERIFIED", 9500)
    assert result.reason_code is None and result.rule_version == 1


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize("filename", ["PAN_Valid.PDF", "Pan_x.jpg", "pAn_y.png", "PAN_1.pdf"])
def test_ac03_matching_is_case_insensitive_on_the_prefix(filename: str) -> None:
    """Spec: matching is case-insensitive on the prefix."""
    assert classify_filename(filename, RULES, 1, ["PAN"]).doc_class == "PAN"


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    "filename", ["random.pdf", "scan001.jpg", "panvalid.pdf", "my_pan_1.pdf", "", "_pan_.pdf"]
)
def test_ac03_3_unmatched_name_is_unrecognised_flagged(filename: str) -> None:
    """AC-03.3: no rule matches -> UNRECOGNISED, FLAGGED, DOC_UNRECOGNISED, 0 bp."""
    result = classify_filename(filename, RULES, 1, ALL_CLASSES)
    assert result.doc_class == "UNRECOGNISED" and result.status == "FLAGGED"
    assert result.reason_code == "DOC_UNRECOGNISED" and result.confidence_bp == 0


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("filename", "accepted"),
    [
        ("utility-bill_1.pdf", ["PAN", "AADHAAR", "PASSPORT"]),
        ("pan_1.pdf", ["AADHAAR", "PASSPORT", "UTILITY_BILL"]),
        ("visa_1.pdf", ["PASSPORT"]),
    ],
)
def test_ac03_4_class_not_accepted_by_item_is_flagged_mismatch(
    filename: str, accepted: list[str]
) -> None:
    """AC-03.4: a recognised class the item does not accept -> FLAGGED, DOC_CLASS_MISMATCH."""
    result = classify_filename(filename, RULES, 1, accepted)
    assert result.status == "FLAGGED" and result.reason_code == "DOC_CLASS_MISMATCH"
    assert result.doc_class != "UNRECOGNISED" and result.confidence_bp == 9500


@pytest.mark.ac("AC-03")
def test_ac03_4_unrecognised_is_never_reported_as_a_mismatch() -> None:
    """AC-03.3 beats AC-03.4: an unknown name keeps DOC_UNRECOGNISED."""
    result = classify_filename("junk.pdf", RULES, 1, ["PAN"])
    assert result.reason_code == "DOC_UNRECOGNISED"


@pytest.mark.ac("AC-03")
def test_ac03_5_results_are_deterministic_and_confidence_is_int() -> None:
    """AC-03.5: same input twice gives identical results; confidence_bp is an int."""
    first = classify_filename("pan_a.pdf", RULES, 1, ["PAN"])
    second = classify_filename("pan_a.pdf", RULES, 1, ["PAN"])
    assert first == second and type(first.confidence_bp) is int


@pytest.mark.ac("AC-03")
def test_ac03_lowest_priority_number_wins_on_overlapping_prefixes() -> None:
    """Rule order is by priority, not by the order rows are supplied."""
    rules = [
        ClassificationRule("pan", "PAN", "VERIFIED", 9500, 2),
        ClassificationRule("pan_special_", "PASSPORT", "VERIFIED", 9000, 1),
    ]
    rule = match_rule("pan_special_1.pdf", rules)
    assert rule is not None and rule.doc_class == "PASSPORT"
    plain = match_rule("pan_1.pdf", rules)
    assert plain is not None and plain.doc_class == "PAN"


@pytest.mark.ac("AC-03")
def test_ac03_a_rule_with_flagged_status_yields_flagged_without_reason() -> None:
    """A seeded FLAGGED rule is honoured as-is (status comes from the rule row)."""
    rules = [ClassificationRule("scan_", "PAN", "FLAGGED", 4000, 1)]
    result = classify_filename("scan_1.pdf", rules, 2, ["PAN"])
    assert (result.status, result.reason_code, result.rule_version) == ("FLAGGED", None, 2)


@pytest.mark.ac("AC-03")
def test_ac03_with_no_rules_everything_is_unrecognised() -> None:
    """An empty rule table degrades safely to UNRECOGNISED."""
    assert classify_filename("pan_1.pdf", [], 0, ["PAN"]).doc_class == "UNRECOGNISED"


@pytest.mark.ac("AC-03")
def test_ac03_8_classifier_takes_no_content_argument() -> None:
    """AC-03.8: the stub reads no file content; its signature has only names and rules."""
    import inspect

    params = set(inspect.signature(classify_filename).parameters)
    assert params == {"filename", "rules", "rule_version", "accepted_classes"}


@pytest.mark.ac("AC-03")
def test_ac03_7_seeded_rules_match_the_spec_table(uow_factory) -> None:  # type: ignore[no-untyped-def]
    """AC-03.7: the repository returns the seeded v1 rules exactly as in the spec table."""
    with uow_factory() as uow:
        version, rules = uow.documents.classification_rules()
    assert version == 1
    assert {(r.prefix, r.doc_class, r.status, r.confidence_bp) for r in rules} == {
        (r.prefix, r.doc_class, "VERIFIED", 9500) for r in RULES
    }
