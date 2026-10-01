"""Stub document classifier (AC-03): decided by file-name prefix only, never by content.

Rules are rows of a migration-seeded table (versioned, append-only). Matching is
case-insensitive; the lowest ``priority`` number wins. Integers only (basis points).
"""

from collections.abc import Iterable
from dataclasses import dataclass

from onboardx.domain.enums import DocClass, DocReasonCode, DocStatus

UNRECOGNISED_CONFIDENCE_BP = 0


@dataclass(frozen=True)
class ClassificationRule:
    prefix: str
    doc_class: str
    status: str
    confidence_bp: int
    priority: int


@dataclass(frozen=True)
class Classification:
    doc_class: str
    status: str
    reason_code: str | None
    confidence_bp: int
    rule_version: int


def match_rule(filename: str, rules: Iterable[ClassificationRule]) -> ClassificationRule | None:
    """First rule (by priority) whose prefix the lower-cased file name starts with."""
    lowered = filename.lower()
    for rule in sorted(rules, key=lambda r: r.priority):
        if lowered.startswith(rule.prefix.lower()):
            return rule
    return None


def classify_filename(
    filename: str,
    rules: Iterable[ClassificationRule],
    rule_version: int,
    accepted_classes: Iterable[str],
) -> Classification:
    """Canned result for a file name; FLAGGED when unrecognised or not accepted by the item."""
    rule = match_rule(filename, rules)
    if rule is None:
        return Classification(
            str(DocClass.UNRECOGNISED),
            str(DocStatus.FLAGGED),
            str(DocReasonCode.DOC_UNRECOGNISED),
            UNRECOGNISED_CONFIDENCE_BP,
            rule_version,
        )
    if rule.doc_class not in set(accepted_classes):
        return Classification(
            rule.doc_class,
            str(DocStatus.FLAGGED),
            str(DocReasonCode.DOC_CLASS_MISMATCH),
            rule.confidence_bp,
            rule_version,
        )
    return Classification(rule.doc_class, rule.status, None, rule.confidence_bp, rule_version)
