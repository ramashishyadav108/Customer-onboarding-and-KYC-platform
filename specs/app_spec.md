# OnboardX Application Spec (root)

Status: DRAFT for human review. Source of truth for acceptance criteria: the capstone brief (AC-01..AC-10, NFR-01..NFR-08). Derived from `specs/brd/brd.md` (approved). Delivery units: `specs/stories/`, `specs/features.json`. Rules: no hand-coded production code, spec is truth, PR-only merges, synthetic data only.

## 1. Overview
OnboardX takes a bank prospect from lead to decision: lead capture, KYC documents per product checklist, stubbed classification, AML/PEP screening, versioned integer risk scoring, auto-approval for clean LOW cases, compliance-officer override for the rest, stubbed account creation, and admin reports. Products: Savings, Current, NRE.

## 2. Approved Decisions
| Topic | Decision |
|---|---|
| Architecture | Option B: explicit persisted state machine; steps are on-demand service functions (screen, classify, decide, advance) triggered by the API |
| Auth | Token-based, seeded synthetic users, roles prospect / kyc-analyst / compliance-officer / admin |
| Notifications | Stubbed, plus status shown in the prospect portal |
| UI | WCAG 2.1 AA; staff UI desktop-first; prospect portal responsive (360 px to 1280 px) |
| Sprint order | 1 lead capture + checklist, 2 document upload + classification stub, 3 screening + risk classification, 4 manual review + account creation, 5 reports + admin console |
| Stack | Fixed in `project-manifest.json` (FastAPI, React/Vite, PostgreSQL, SQLite in tests) |

## 3. Proposed for Review (not yet approved)
1. Risk weights and thresholds (integer only): weights age 20, income 25, occupation 30, geography 25 (sum 100). Score = sum(points * weight) // 100. Bands: LOW 0-29, MEDIUM 30-59, HIGH 60-100. Full tables in `specs/classification_spec.md`.
2. Auto-approval target: at least 60 percent (6000 bp) of decided cases in the 200-case synthetic demo cohort end APPROVED with decision type AUTO.
3. Stub classifier recognises seven classes (PAN, AADHAAR, PASSPORT, UTILITY_BILL from the brief, plus PHOTOGRAPH, GST_CERTIFICATE, VISA so Current and NRE checklists can be satisfied).
4. Screening hits do not add a SCREENED->MANUAL_REVIEW edge: the hit is recorded at SCREENED, the case proceeds to CLASSIFIED, and the decision step routes it to MANUAL_REVIEW with AML_HIT or PEP_HIT. This keeps the lifecycle in AC-04 exact.
5. A profile step (date of birth, annual income, occupation category, country code) is captured after lead creation because AC-06 needs these inputs and AC-01 only collects name, contact and product.
6. Checklist editing in the admin console is out of scope for v1; checklists change by append-only migration. Rule sets and watchlist are admin-managed.

## 4. Lifecycle (AC-04)
States: INITIATED, DOCS_SUBMITTED, SCREENED, CLASSIFIED, APPROVED, REJECTED, MANUAL_REVIEW.

| From | Allowed to |
|---|---|
| INITIATED | DOCS_SUBMITTED |
| DOCS_SUBMITTED | SCREENED |
| SCREENED | CLASSIFIED |
| CLASSIFIED | APPROVED, REJECTED, MANUAL_REVIEW |
| MANUAL_REVIEW | APPROVED, REJECTED |
| APPROVED, REJECTED | none (terminal) |

Any other transition raises `InvalidOnboardingStateException` (API 409 `INVALID_STATE`). Transitions are idempotent by key and write a state-history row atomically.

## 5. Roles
| Role | Can |
|---|---|
| prospect | Register lead, edit own profile, upload and re-upload own documents, submit, view own status and notifications |
| kyc-analyst | Read all cases and documents, reject documents with reason, trigger screen and classify |
| compliance-officer | Review queue, override MANUAL_REVIEW, reclassify with reason |
| admin | Rule sets, watchlist, reports, read all cases |

## 6. Acceptance Criteria

### AC-01 Lead registration
- AC-01.1 POST /api/v1/leads with name, contact, product in {Savings, Current, NRE} returns 201, a UUID `case_id` and state INITIATED.
- AC-01.2 Invalid or missing fields return 422 and create nothing.
- AC-01.3 Detail in `specs/lead-capture_spec.md`.

### AC-02 KYC documents and checklist
- AC-02.1 Each product has a checklist (ID proof, address proof, photograph plus product-specific items).
- AC-02.2 Submission with any mandatory item missing is blocked (422 MISSING_DOCUMENTS). Detail in `specs/document-checklist_spec.md`.

### AC-03 Stubbed document classification
- AC-03.1 Canned results for known fixtures (PAN, Aadhaar, passport, utility-bill); AC-03.2 unrecognised files are flagged. Detail in `specs/document-classification-stub_spec.md`.

### AC-04 Lifecycle
- AC-04.1 Only the transitions in section 4 succeed.
- AC-04.2 Every other transition raises `InvalidOnboardingStateException` with case_id, from_state, to_state.
- AC-04.3 Every transition is recorded atomically in append-only state history.

### AC-05 AML/PEP screening
- AC-05.1 Name screened against the static watchlist; AC-05.2 a hit leads to MANUAL_REVIEW with reason code AML_HIT or PEP_HIT. Detail in `specs/screening_spec.md`.

### AC-06 Versioned risk rules
- AC-06.1 Rules over age, income band, occupation category and geography give LOW, MEDIUM or HIGH; AC-06.2 published versions are immutable. Detail in `specs/classification_spec.md`.

### AC-07 Auto-approval and account stub
- AC-07.1 LOW risk, no hit and all documents verified give APPROVED plus stub account creation. Detail in `specs/account-creation-stub_spec.md` and `specs/manual-review_spec.md`.

### AC-08 Override
- AC-08.1 Compliance officer overrides MANUAL_REVIEW with APPROVE or REJECT, a reason code, fully audited. Detail in `specs/manual-review_spec.md`.

### AC-09 Notifications and re-upload
- AC-09.1 A stubbed notification is recorded at each transition (INITIATED, DOCS_SUBMITTED, SCREENED, CLASSIFIED, APPROVED, REJECTED, MANUAL_REVIEW).
- AC-09.2 A document rejection notifies the prospect with item and reason codes.
- AC-09.3 The prospect re-uploads missing or rejected documents as a new version without restarting the case (detail in `specs/document-checklist_spec.md`).
- AC-09.4 Notifications are visible on the portal status page.

### AC-10 Admin reporting
- AC-10.1 Admin sees TAT by product, approval funnel, manual-review backlog, average time per stage and top rejection reasons. Detail in `specs/reports_spec.md`.

## 7. Non-Functional Requirements
| ID | Requirement | Enforced by |
|---|---|---|
| NFR-01 | Risk thresholds and weights are integer or fixed-point, never float | E3-S2, E3-S3, E5-S1, E5-S5 |
| NFR-02 | KYC documents, screening results, decisions and overrides are append-only | E1-S4, E2-S3, E3-S1, E4-S1..S3, E5-S5 |
| NFR-03 | No plaintext PII (PAN, Aadhaar, contact, income, occupation) in logs | E1-S1, E4-S4, E5-S5 |
| NFR-04 | Auth at the controller layer; four separated roles | E1-S2, E3-S4, E4-S3, E5-S3 |
| NFR-05 | DB, classification-rule and watchlist migrations are append-only | E1-S1 (guard), E1-S5, E2-S3, E3-S1 |
| NFR-06 | Structured JSON logs with correlation IDs and case_id | E1-S1 |
| NFR-07 | /health returns 200 within 1 s of startup | E1-S1 |
| NFR-08 | Architecture rules as tests: published rules immutable, approved case unmodifiable, band reassignment needs an override audit record | E3-S2, E4-S1, E4-S3, E5-S5 |

## 8. Story and Sprint Map
| Sprint | Epic | Stories |
|---|---|---|
| 1 | E1 Lead Capture, Foundation and Checklist | E1-S1..E1-S5 |
| 2 | E2 Document Upload and Classification Stub | E2-S1..E2-S5 |
| 3 | E3 Screening and Risk Classification | E3-S1..E3-S5 |
| 4 | E4 Manual Review, Decisions and Account Creation | E4-S1..E4-S5 |
| 5 | E5 Reports and Admin Console | E5-S1..E5-S5 |

Execution order follows `specs/stories/dependency-graph.md` (groups A to L). Some later-sprint foundations (E4-S2 account stub, E4-S4 notifications, E5-S1 metrics) have no early dependencies and may run in early groups; sprint order governs what is delivered and reviewed first.

## 9. Feature Specs
`lead-capture_spec.md`, `document-checklist_spec.md`, `document-classification-stub_spec.md`, `screening_spec.md`, `classification_spec.md`, `manual-review_spec.md`, `account-creation-stub_spec.md`, `reports_spec.md`, all in `specs/`.

## 10. Conventions
- API base `/api/v1`; errors are `{ "error": { "code", "message", "details" } }`; provisional paths, finalised in `/design`.
- Timestamps UTC ISO-8601. Money is integer INR. Scores and rates are integers (basis points for ratios).
- Synthetic fixtures live in `tests/fixtures` (documents named per the classifier convention).
