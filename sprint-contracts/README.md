# Sprint contracts: provenance

All files validate against `.claude/skills/evaluation/references/contract-schema.json`. The schema forbids extra properties, so approval and provenance are recorded here, not in the JSON.

| File | Authored | Stories | Features |
|---|---|---|---|
| `group-A.json` | Negotiated before implementation (real harness-format contract) | E1-S1, E1-S4, E1-S5, E3-S2 | F001-F009, F028-F042, F085-F092 |
| `sprint-2-documents.json` | Retrospectively, after implementation | E2-S1..E2-S5 (API checks only; UI features F069-F074 excluded) | F043-F068 |
| `sprint-3-screening-risk.json` | Retrospectively, after implementation | E3-S1, E3-S3, E3-S4 | F075-F084, F093-F107 |
| `sprint-4-review-account.json` | Retrospectively, after implementation | E4-S1..E4-S4 (E4-S5 UI excluded) | F114-F144 |
| `sprint-5-reports-admin.json` | Retrospectively, after implementation | E5-S1..E5-S5 (E5-S4 dashboard UI features F167-F171 excluded; E5-S5 proven via pytest/architecture checks) | F151-F166, F172-F177 |
| `ui-groups-F-H-J-L.json` | Retrospectively, after implementation; executed by `e2e/live/ui-groups.live.ts` against a live backend (`playwright.live.config.ts`) | E2-S5, E3-S5, E4-S5, E5-S4 (UI) | F069-F074, F108-F113, F145-F150, F167-F171 |

## Important caveat

The contracts for sprints 2-5 were authored retrospectively, after the implementation existed, by probing the running backend and reading the specs. They were not negotiated with the evaluator before coding, so they are weaker evidence than group A's: the expected statuses and codes were observed from the implementation, then cross-checked against the specs. Treat any mismatch as a prompt to decide whether the spec or the code is wrong, not as automatic proof either way.

## Conventions

- Base URL assumption: `http://127.0.0.1:8010` (throwaway eval DB). Staff demo logins: `analyst1`, `officer1`, `admin1` with password `demo-<username>-pass`.
- Checks are single requests; multi-step preconditions (create lead, profile, uploads, submit) are described in each check's description. Submit auto-advances the pipeline, so a clean Case A reaches APPROVED and Test Person One reaches MANUAL_REVIEW (AML_HIT) without separate staff calls.
- The feature list for UI-only features (Playwright/axe) is deliberately excluded from sprints 2, 4 and 5; they need a separate contract.
