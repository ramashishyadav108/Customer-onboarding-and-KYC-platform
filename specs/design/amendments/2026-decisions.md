# Design Decision Resolutions

Status: accepted by the user (option A, "accept recommendations").

| ID | Decision |
|----|----------|
| DD-2, DD-4 | Proposed document-reject and reclassify reason-code lists accepted. |
| DD-6 | `POST /leads` is public and returns a case-bound prospect token. Accepted. |
| DD-7 | `GET /cases` and `GET /cases/{id}/evidence` added. Accepted. |
| DD-13 | `AUTO_ADVANCE_ON_SUBMIT` defaults to **on**. |
| DD-14 | Profile gains `state_code` (required when `country_code` is IN). `DOMESTIC_BORDER` = IN + state in the seeded synthetic list `JK, PB, AS`. |
| DD-15 | Backend uses `venv` + pip + `requirements.lock`. `uv` is not installed on this machine; `project-manifest.json`, `init.sh`, `CLAUDE.md` were updated to match. |
| DD-16 | E1-S1 runs first within Group A (dependency-graph amendment accepted). |
| Screening hit | A hit is recorded at SCREENED; the case continues to CLASSIFIED; the decision step routes it to MANUAL_REVIEW with `AML_HIT` / `PEP_HIT`. No SCREENED -> MANUAL_REVIEW edge. |

## Follow-ups for the build agents (spec is truth)
- Add `state_code` to the profile in `api-contracts.*`, `data-models.*` and migration 0001.
- Seed the `DOMESTIC_BORDER` state list in the classification rule-set migration (append-only).
- Add tests tagged AC-01 (state required for IN) and AC-06 (border-state branch).
