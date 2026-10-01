# Evaluation: all groups (2026-10-01)

Verdict: PASS. 177 of 177 features pass; 3 of them (F025, F108, F167) pass against a corrected spec, not the original wording (see below).

## What was run
| Layer | Scope | Result |
|---|---|---|
| Live API, throwaway backend :8010 | group A, sprints 3, 4, 5 contracts (69 api_checks, 9 performance checks) by evaluator agent | 69/69 and 9/9 |
| Live API | sprint 2 contract (earlier run, :8000) and groups B, C (F010-F027) | pass; F012, F013 checked by DB query, F015 by static scan, F016, F022 by pytest |
| Live UI, Playwright + axe-core (`e2e/live/ui-groups.live.ts`, config `e2e/playwright.live.config.ts`) | groups F, H, J, L (F069-F074, F108-F113, F145-F150, F167-F171) against real backend :8010 and Vite :3010 | 21/21 |
| Backend | pytest, ruff, mypy | 1318 passed, 1 skipped (Windows symlink test); coverage 97.8%; clean |
| Frontend | vitest, eslint, tsc, coverage | 112 passed; clean; statements 96.82% (floor 80%) |

## Defects found and fixed
1. Frontend coverage 79.81% < 80% floor: added tests for App routing, shell, status, case detail and rule-set pages.
2. Backend 500 on `GET /cases/{id}/evidence` under parallel reads with `DATABASE_URL=sqlite:///:memory:` (shared single connection used by several worker threads). Regression test `test_in_memory_concurrency.py` (red first), fix: `make_uow_factory(serialize=True)` for in-memory engines.
3. E2-S5 AC3: status page lacked an in-place Re-upload control. Added `ReuploadList` with unit tests.
4. E4-S5 AC3: approve confirmation omitted the account number. Fixed with test.

## Passed against a corrected spec (user-approved)
Strictly against the original step wording these three would FAIL. The user chose to keep the corrections (option 1, 2026-10-01); the wording below is now the spec.
| Feature | Original step | Corrected step | Basis |
|---|---|---|---|
| F025 | GET returns the stored profile to staff | prospect GET returns the profile; staff GET returns `profile: null`, `profile_complete: true` | DD-5 in `specs/design/system-design.md` and `api-contracts.md`; backend tests `test_ac01_4_staff_view_hides_the_profile` |
| F108 | filter SCREENED + NRE | filter INITIATED + NRE | submit auto-advances, so SCREENED is never a resting state |
| F167 | five panels | six panels (five AC-10 reports + auto-approval rate) | `ReportPanels.tsx`, AC-10 plus E5 auto-approval target |

## Spec corrections (Spec-Is-Truth)
- F025: staff receive `profile: null` by design decision DD-5 (`specs/design/system-design.md`, `api-contracts.md`); feature step text corrected, code unchanged.
- F167: dashboard has six panels (five AC-10 reports plus auto-approval); text corrected.
- S5-API-03 contract wording clarified: `buckets` is a list.

## Deviations and limits
- F170 (empty database) ran against a freshly started in-memory backend.
- Mocked e2e suite (16 tests) unchanged; live suite is separate (`*.live.ts`).
- Design-critic not run (contracts have no design_checks). Playwright MCP unavailable in this session; the Playwright test runner was used instead.
- F165 (p95 on 1,000 cases) and the group-A file-existence/frontend_toolchain checks were covered only through the passing pytest suite.

## Addendum: admin management and queries (AC-11 to AC-13), 2026-10-01
Scope added after the brief was re-read: admin user and role management, admin checklist versions, analyst queries (spec: `specs/admin-management_spec.md`, contract: `sprint-contracts/sprint-6-admin-management.json`, features F178-F197).

| Check | Result |
|---|---|
| New backend tests (`test_admin_users_api.py`, `test_admin_checklists_api.py`, `test_queries_api.py`, role-matrix rows) | 49 plus 11 matrix rows, all pass |
| Backend full suite with coverage | 1404 passed, 1 skipped (Windows symlink test), coverage 98.02%, `ruff`, `mypy`, `lint-imports` clean |
| Frontend vitest, `eslint`, `tsc`, coverage | 132 passed, clean, 97.28% statements |
| Live Playwright against a fresh real backend (`e2e/live/`) | 34 of 34: the earlier 21 plus 13 in `ui-management.live.ts` (users, checklists, queries, role boundary, axe) |
| Mocked e2e | 16 of 16, no snapshot changes |

Behaviour change to note: staff tokens are now honoured only for an existing, active user and carry that user's stored role (AC-11.4, AC-11.5). One existing test minted a staff token for a user that did not exist; it now logs in as a seeded user. Migration-head assertions moved from 0007 to 0008 (new append-only migration; earlier migrations untouched).

Limits: the three append-only and PII properties of queries (F195) and the audit rows are proven by pytest only (no HTTP surface). The last-active-admin rule (`LAST_ADMIN`) cannot be reached through the API by an active admin because self-modification is blocked first; it is tested at service level. Admin password reset and prospect user management are not part of this scope.

## Addendum: sign-up, staff approval and review policy (AC-14, AC-15), 2026-10-01
Triggered by a user observation: a customer who signed up and uploaded documents was approved with no human involved. That is the brief's AC-07 (auto-approve a clean LOW-risk case); screening did run, automatically, as the rule-based engine (AC-05). Two changes followed (spec: `specs/admin-management_spec.md`; contracts: `sprint-7-accounts.json`, `sprint-8-staff-signup-review-policy.json`; features F198-F214).

| Check | Result |
|---|---|
| Backend full suite | 1452 passed on the full run; the 4 failures were migration-head assertions (0008 to 0009), updated and rerun (358 passed in that subset); `ruff`, `mypy`, import-linter clean |
| Frontend | 154 vitest passed, 97.46% statements; `eslint` and `tsc` clean; mocked e2e 16 of 16 |
| Live Playwright, auto policy (real backend) | 46 passed, 2 skipped by design (manual-policy file) |
| Live Playwright, `REVIEW_POLICY=manual` backend | 2 of 2: clean application waits, officer approves, customer has an account |

Decisions recorded: (1) Review policy is a setting. `auto` stays the default because the brief requires auto-approval and the 60 percent target; `manual` makes the compliance officer decide every case (reason `MANUAL_POLICY`). (2) Sign-up asks for an account type, but a staff role never grants access by itself: it is created inactive and pending, with no token, until an admin approves it. Granting self-selected admin rights at sign-up would defeat NFR-04. Migration 0009 rebuilds the append-only `decisions` table to allow the new reason and adds `users.pending`.

Not done: case assignment to a named person (claiming a case). Cases are routed by queue (analyst workbench for documents and queries, officer queue for decisions), not assigned to individuals.

### Addendum: open admin sign-up (AC-14.11), 2026-10-01
Requested: an Admin sign-up should not wait for approval, while KYC analyst and compliance officer should. Built as the setting `ADMIN_SIGNUP` (`approval` default, `open`), because open admin sign-up lets anyone who reaches the page take full control; the user's local server runs with `open`. Evidence: backend `test_staff_approval_api.py` (5 new tests), 157 frontend tests (97.47% statements), mocked e2e 16 of 16, live suite 46 passed (5 skipped by design) on the default stack, and 5 of 5 on a stack started with `ADMIN_SIGNUP=open REVIEW_POLICY=manual` (`ui-zmanual`, `ui-zopen-admin`). Features F215-F218.
