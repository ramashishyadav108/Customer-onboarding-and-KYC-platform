# Manual Review and Decision Spec

Stories: E4-S1 (primary), E4-S3, E4-S4, E4-S5, E5-S5. Features: F114-F122, F129-F150, F172-F177.

## Purpose
The decision step turns a CLASSIFIED case into APPROVED or MANUAL_REVIEW. Compliance officers resolve MANUAL_REVIEW with an audited override. Notifications are stubbed.

## Decision rules
On a CLASSIFIED case:
1. APPROVED (decision type AUTO, reason AUTO_APPROVED) only if band is LOW, there is no screening hit, and every current document is VERIFIED. The stub account is created in the same transaction.
2. Otherwise MANUAL_REVIEW with the first matching reason code: AML_HIT or PEP_HIT, then DOC_UNRECOGNISED, then RISK_MEDIUM, then RISK_HIGH.

`POST /api/v1/cases/{id}/advance` runs screen, classify, decide in order and is idempotent.

## Override reason codes (controlled list, proposed)
Approve: FALSE_POSITIVE_CLEARED, RISK_ACCEPTED, DOCS_CONFIRMED. Reject: CONFIRMED_WATCHLIST_MATCH, DOCS_INSUFFICIENT, RISK_TOO_HIGH, POLICY_OTHER.

## Endpoints (provisional)
| Method and path | Role |
|---|---|
| POST /api/v1/cases/{id}/decide | system, kyc-analyst, admin |
| POST /api/v1/cases/{id}/advance | system, kyc-analyst, admin |
| GET /api/v1/review-queue | compliance-officer |
| POST /api/v1/cases/{id}/override | compliance-officer |
| POST /api/v1/cases/{id}/reclassify | compliance-officer |
| GET /api/v1/cases/{id}/notifications | owning prospect |

## Acceptance Criteria

### AC-07 (decision part) LOW risk, no AML hit and all documents verified give APPROVED plus stubbed account creation
- AC-07.1 A clean LOW case is approved, a decision row (AUTO, AUTO_APPROVED, rule_version) is written and an account exists.
- AC-07.2 Hit, unverified document, MEDIUM or HIGH route to MANUAL_REVIEW with codes in the precedence above and create no account.
- AC-07.3 An APPROVED case is unmodifiable (CaseLockedError, API 409 CASE_LOCKED) (NFR-08).
- AC-07.4 Decision rows are append-only; repeated decide returns the original decision.
- AC-07.5 advance drives a clean submitted case to APPROVED with history SCREENED, CLASSIFIED, APPROVED and is idempotent.

### AC-08 Compliance officer overrides MANUAL_REVIEW (APPROVE or REJECT) with reason code, audited
- AC-08.1 The review queue lists MANUAL_REVIEW cases oldest first with reason code and age_minutes; only compliance-officer may read it.
- AC-08.2 Override with APPROVE or REJECT and a valid reason code changes state; missing or unknown reason returns 422 and changes nothing.
- AC-08.3 Analyst, admin and prospect get 403; a case not in MANUAL_REVIEW returns 409 INVALID_STATE.
- AC-08.4 An append-only Override row and an OVERRIDE_APPLIED audit entry are written with actor, previous state, decision, reason code, rule_version.
- AC-08.5 APPROVE creates the stub account; REJECT does not.
- AC-08.6 Risk-band reassignment (reclassify) requires a reason code and produces a new assessment plus audit record (NFR-08).
- AC-08.7 UI: queue and review panel; buttons disabled until a reason code is selected; dialog focus handling; WCAG 2.1 AA.

### AC-09 (notification part) Stubbed notification at each transition
- AC-09.1 Exactly one Notification per state entered (INITIATED to MANUAL_REVIEW, APPROVED, REJECTED).
- AC-09.2 A document rejection records DOC_REJECTED with item and reason codes.
- AC-09.4 The owning prospect reads notifications newest first; others get 403; the portal status page shows them.
- AC-09.5 Notification records and logs contain no plaintext contact; a sender failure does not roll back the transition and is logged with correlation_id and case_id.

## Non-functional notes
NFR-02 (decisions and overrides append-only), NFR-03, NFR-04, NFR-08.
