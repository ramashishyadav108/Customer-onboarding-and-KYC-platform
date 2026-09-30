# Screening Spec (AML/PEP)

Stories: E3-S1 (primary), E3-S4 (watchlist admin), E3-S5 (UI). Features: F075-F084, F100-F107, F108-F113.

## Purpose
Compare the applicant name with a static synthetic watchlist. A hit sets a routing flag and reason code; the decision step (see `manual-review_spec.md`) sends the case to MANUAL_REVIEW.

## Watchlist
Entry: entry_id, name, aliases[], list_type (AML | PEP), active-from, deactivated-at. Seeded by append-only migration with at least 10 synthetic entries (5 AML, 5 PEP). Admin additions and deactivations append rows; nothing is edited or deleted.

## Matching (v1)
Normalise: Unicode NFKC, lowercase, strip punctuation, collapse whitespace, split into tokens and sort. A case matches an entry when its normalised token list equals that of the entry name or any alias. No fuzzy matching in v1.

## Endpoint (provisional)
POST /api/v1/cases/{id}/screen (kyc-analyst, admin): DOCS_SUBMITTED to SCREENED; idempotent on SCREENED with unchanged watchlist version.

## Result
`{id, case_id, hits:[{entry_id, list_type, reason_code}], requires_manual_review, watchlist_version, screened_at}`. Reason codes AML_HIT, PEP_HIT.

## Acceptance Criteria

### AC-05 AML/PEP screening of name against static watchlist; hit leads to MANUAL_REVIEW with reason code
- AC-05.1 Screening a DOCS_SUBMITTED case stores a ScreeningResult and moves the case to SCREENED.
- AC-05.2 Variants of a watchlist name that differ by case, punctuation, spacing or token order hit; an unrelated name does not.
- AC-05.3 A hit records entry_id, list_type and reason_code (AML_HIT or PEP_HIT) and sets `requires_manual_review`.
- AC-05.4 A case with a hit is never auto-approved; the decision step routes it to MANUAL_REVIEW with the hit's reason code (verified by E4-S1 features F115, F117).
- AC-05.5 A clean result has an empty hit list and `requires_manual_review` false.
- AC-05.6 Screening from any state except DOCS_SUBMITTED returns 409 INVALID_STATE; repeat on SCREENED is idempotent.
- AC-05.7 Screening results are append-only; re-screening adds a row.
- AC-05.8 Watchlist seed and changes are append-only migrations or appended rows (NFR-05).
- AC-05.9 Admin can add and deactivate entries via API and UI; later screening honours the change; changes are audited.
- AC-05.10 Logs record case_id and hit count only, never the applicant name together with list details.

## Non-functional notes
NFR-02, NFR-04 (admin-only management), NFR-05.
