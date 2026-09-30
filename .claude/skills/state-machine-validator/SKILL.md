---
name: state-machine-validator
description: Validates the onboarding lifecycle state machine and its guards (AC-04, NFR-08). Use when touching case states or transitions.
---

# state-machine-validator

Allowed transitions (AC-04):
INITIATED -> DOCS_SUBMITTED -> SCREENED -> CLASSIFIED -> APPROVED | REJECTED | MANUAL_REVIEW.
MANUAL_REVIEW -> APPROVED | REJECTED (compliance override only, audited, AC-08).
APPROVED and REJECTED are terminal; an approved case cannot be modified (NFR-08).

## Rules
- All transitions go through one domain function; invalid ones raise `InvalidOnboardingStateException`.
- Every transition appends a state-history row (NFR-02) and emits a stubbed notification (AC-09).
- Re-upload of documents must not restart the case (AC-09).

## Validation procedure
1. Enumerate the full (from, to) matrix in a parametrised test; assert exactly the allowed set passes.
2. Assert each invalid pair raises `InvalidOnboardingStateException`.
3. Assert mutation attempts on APPROVED cases are refused.
4. Tag tests with AC-04 / NFR-08.
