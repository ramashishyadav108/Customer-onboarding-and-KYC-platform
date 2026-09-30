# OnboardX - Business Case (BC-AINE-019)

## Problem
A bank takes about seven days to onboard a new retail customer. Document checks, name screening and risk assessment are largely manual, so applicants drop off, staff time is consumed by routine cases, and screening and audit quality vary. The bank wants turnaround under one hour without weakening compliance.

## Target users
| Role | Need |
|------|------|
| Prospect | Register, upload the right documents once, see status and reasons, re-upload without restarting |
| KYC analyst | Review submitted documents, mark each VERIFIED or REJECTED with a reason, raise queries |
| Compliance officer | Work the manual-review queue (AML/PEP hits, ambiguous cases) and override with a reason code and audit trail |
| Admin | Maintain product checklists, rule library and watchlist; see turnaround, funnel, backlog and rejection reasons |

## Value proposition
Clean, low-risk cases are approved automatically in minutes; risky or ambiguous cases are routed to a human with full evidence; every decision is reproducible because rules are versioned and every action is recorded append-only.

## Success metrics
- Onboarding turnaround from ~7 days to under 1 hour for auto-approved cases.
- At least 60% of decided cases in the synthetic cohort auto-approved (proposed target, 6000 basis points).
- 100% of decisions and overrides have an audit record with actor and reason code.
- Every AC-01..AC-10 and NFR-01..NFR-08 has at least one test; coverage at least 80%.

## Domain rules
1. Lifecycle: INITIATED -> DOCS_SUBMITTED -> SCREENED -> CLASSIFIED -> APPROVED | REJECTED | MANUAL_REVIEW; invalid transitions raise `InvalidOnboardingStateException`.
2. Products: Savings, Current, NRE, each with a document checklist; missing documents block submission.
3. Document classification is stubbed and returns canned results for known fixtures; unknown uploads are flagged.
4. AML/PEP screening compares the name to a static watchlist; any hit leads to MANUAL_REVIEW with a reason code.
5. Risk band (LOW/MEDIUM/HIGH) comes from a versioned rule engine over age, income band, occupation and geography; published versions are immutable; all arithmetic is integer.
6. Auto-approval only for LOW risk, no AML hit and all documents verified; account creation is stubbed.
7. Compliance override (APPROVE/REJECT) needs a reason code and is audited; an approved case cannot be modified; band reassignment needs an override record.
8. Documents, screening results, decisions, overrides and migrations are append-only; PII never appears in plaintext logs.

## Out of scope
Real OCR, CKYC/e-KYC, video KYC, e-sign, real core-banking account creation, production deployment.

## Constraints
No hand-written production code (agents generate all code and tests); specs win over code; all changes merge through pull requests; synthetic data only.
