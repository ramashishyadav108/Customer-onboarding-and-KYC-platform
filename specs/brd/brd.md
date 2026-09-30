# BRD: OnboardX - Customer Onboarding and KYC Platform

Status: DRAFT, awaiting human approval. Items marked ASSUMED were not stated in the brief and need confirmation.

## 1. Executive Summary
OnboardX is a digital onboarding and KYC pipeline for a bank. It replaces a roughly 7-day manual process (document checks, screening) with an automated flow targeting under 1 hour turnaround. Low-risk cases with no AML hit are auto-approved. Everything else goes to a compliance officer, and every decision and override is audited. It is a capstone project: all code is agent-generated, data is synthetic only.

## 2. Problem Statement
Bank onboarding takes about 7 days because document verification and AML/PEP screening are manual. Consequences: customer drop-off, high manual effort, and compliance risk from inconsistent screening and missing audit trails.

## 3. Target Users
| Role | Profile | Primary surface |
|------|---------|-----------------|
| Prospect | Non-technical applicant | Web portal (lead capture, document upload, status) |
| KYC analyst | Operations staff | Document workbench |
| Compliance officer | Compliance staff | MANUAL_REVIEW queue, audited overrides |
| Admin | Platform administrator | Admin console: checklists, rules, watchlist, reports |

## 4. Success Metrics
- Turnaround time: 7 days down to under 1 hour.
- LOW-risk, no-AML-hit cases are auto-approved (target rate: ASSUMED, to be set in /spec).
- 100% of decisions and overrides written to an audit trail.
- Capstone bar: all 10 acceptance criteria (AC-01..AC-10) and 8 non-functional requirements (NFR-01..NFR-08) tested; backend and frontend coverage at or above 80%; rubric evidence trail complete.
- Note: the AC and NFR texts are not yet in the repo. They must be supplied or defined in /spec (see Open Questions).

## 5. Scope
In scope:
- Lead capture
- Document checklist and KYC document upload
- Document classification (stub)
- AML/PEP screening (against admin-managed watchlist)
- Risk classification with versioned rules (integer/fixed-point arithmetic only, no floats)
- Manual review and audited override
- Account creation (stub)
- Reports and admin console

Out of scope (v1): real OCR, CKYC/e-KYC, video KYC/liveness, e-signature, real core banking integration, production deployment, secrets management, multi-region.

## 6. MVP Definition
Smallest end-to-end slice: prospect submits lead for one product (Savings), uploads checklist documents, stub classifier tags them, screening runs, rule-based risk band is computed, LOW/no-hit case is auto-APPROVED with stub account created, and otherwise lands in MANUAL_REVIEW where a compliance officer approves or rejects with an audit entry. Current/NRE products, full admin rule/watchlist editing and reports follow after the slice works (ASSUMED sequencing; /spec to finalize).

Lifecycle states: INITIATED -> DOCS_SUBMITTED -> SCREENED -> CLASSIFIED -> APPROVED | REJECTED | MANUAL_REVIEW. Products: Savings, Current, NRE.

## 7. Alternatives Considered
Stack is fixed by `project-manifest.json`, so alternatives concern the workflow and rules design.

| Option | Description | Pros | Cons | Fit |
|--------|-------------|------|------|-----|
| A. Synchronous pipeline | Each transition runs inline in the API call | Simplest, deterministic tests | Blocks requests; poor if screening is slow | Capstone scale |
| B. Explicit state machine with service-layer steps, run on demand (chosen, ASSUMED) | Persisted state + transition table; each step is a service function triggered by API/event, idempotent | Clear audit, testable transitions, fits layered architecture, no extra infra | Slightly more design than A | Capstone with audit emphasis |
| C. Async queue/workers | Message broker drives steps | Scales, resilient | Extra infra, out of scope for local deploy, harder to test | Production |

Chosen: B, because it gives auditable, testable lifecycle transitions without new infrastructure. Rejected A (weak separation of steps) and C (infra and complexity beyond local-only deployment). Needs user confirmation.

## 8. Technical Architecture
Fixed by manifest: Python 3.12 + FastAPI (uv, ruff, mypy, pytest); React + TypeScript + Vite (vitest, eslint); PostgreSQL (SQLite in tests); local deployment (backend :8000, frontend :3000, health at /health). Strict layered architecture Types -> Config -> Repository -> Service -> API -> UI, one-way imports. Rules: no hand-coding, spec is truth, PR-only merges, TDD, functions under 50 lines, files under 300. Risk rules versioned and evaluated with integers/fixed-point only.

## 9. Data Model Overview (draft)
Lead/Applicant, Application (state, product, risk band, rules version), Document (type, classification, status), ChecklistTemplate (per product), ScreeningResult (hits, watchlist entry refs), WatchlistEntry, RiskRuleSet (version, rules), ReviewDecision/Override (actor, reason, timestamp), AuditLog (append-only), Account (stub), User/Role.

## 10. External Integrations
None real. Document classifier, account creation, and screening provider are stubs/local. Watchlist is admin-managed synthetic data.

## 11. Edge Cases and Constraints
- Synthetic data only; no real PII. Still model PII handling (masking in logs, role-based access) as if real (ASSUMED).
- Missing/illegible/wrong documents: application stays in DOCS state, prospect notified in portal.
- Classifier stub mismatch: routes to analyst.
- Screening hit (AML/PEP) or non-LOW risk: MANUAL_REVIEW, never auto-approved.
- Rule version changes: existing decisions retain the version they used; reclassification is explicit and audited.
- Override requires role, reason, and audit entry; audit log is append-only.
- Invalid state transitions rejected; repeated calls idempotent.
- Fixed-point arithmetic avoids rounding ambiguity in scores.
- Failure notification mechanism (UI status only vs email) ASSUMED UI-only for v1.
- Constraints: local deployment, no uptime SLA, no budget beyond dev tooling.

## 12. UI Context
Web UI with four role-specific areas: prospect portal, analyst document workbench, compliance review queue, admin console (checklists, rules, watchlist, reports). Desktop-first for staff; prospect portal responsive (ASSUMED). Accessibility target WCAG 2.1 AA (ASSUMED). Mockups to be produced in /design; no existing brand guidelines provided.

## 13. Open Questions
1. Definitions of AC-01..AC-10 and NFR-01..NFR-08 are not in the repo; provide them or confirm /spec should draft them.
2. Confirm alternative B (state machine, on-demand steps).
3. Risk bands (LOW/MEDIUM/HIGH?) and initial scoring factors and thresholds.
4. Auto-approval target rate.
5. Authentication approach for four roles (simple local auth assumed).
6. Notification channel for prospects.
7. Confirm WCAG level and device support.
8. Confirm MVP sequencing (Savings first).
