---
name: ac-trace
description: Report which AC-NN / NFR-NN ids have tests referencing them and which do not.
---

# /ac-trace

1. Extract every `AC-NN` and `NFR-NN` id from `specs/app_spec.md` and `specs/*_spec.md`.
2. Grep `backend/tests`, `tests`, `frontend/src` and `e2e` for each id.
3. Print a table: id | spec | test files | status (COVERED / MISSING).
4. Write the table to `specs/reviews/ac-trace.md`, MISSING ids first.
5. Do not write production code; for missing ids, name the story group that should add the tests.
