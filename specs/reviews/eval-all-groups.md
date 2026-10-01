# Evaluation: all groups (2026-10-01)

Verdict: PASS. 177 of 177 features pass.

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

## Spec corrections (Spec-Is-Truth)
- F025: staff receive `profile: null` by design decision DD-5 (`specs/design/system-design.md`, `api-contracts.md`); feature step text corrected, code unchanged.
- F167: dashboard has six panels (five AC-10 reports plus auto-approval); text corrected.
- S5-API-03 contract wording clarified: `buckets` is a list.

## Deviations and limits
- F108 filters INITIATED + NRE rather than SCREENED + NRE: submit auto-advances the pipeline, so SCREENED is not a resting state.
- F170 (empty database) ran against a freshly started in-memory backend.
- Mocked e2e suite (16 tests) unchanged; live suite is separate (`*.live.ts`).
- Design-critic not run (contracts have no design_checks). Playwright MCP unavailable in this session; the Playwright test runner was used instead.
- F165 (p95 on 1,000 cases) and the group-A file-existence/frontend_toolchain checks were covered only through the passing pytest suite.
