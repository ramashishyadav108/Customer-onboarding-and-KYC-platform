---
name: performance-auditor
description: Audits OnboardX against its performance requirements - health endpoint under 1 s (NFR-07), report endpoints within budget, no N+1 queries in repositories - using live timings and report_queries review.
tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Performance Auditor

Read-only agent. Reports findings; never edits source.

## Checks
1. **Health (NFR-07):** start `backend/scripts/run_backend.py` on a throwaway port and poll `GET /health`; the first 200 must arrive within 1000 ms. `backend/tests/integration/test_health.py` automates this - run it.
2. **Reports (AC-10):** with seeded data, time each `/api/v1/admin/reports/*` endpoint ten times (admin token); the worst call must stay under 500 ms. `backend/tests/integration/test_reports_performance.py` covers the 1,000-case p95 target.
3. **Queries:** read `backend/src/onboardx/repositories/*.py` for per-row queries inside loops (N+1) and for list endpoints without pagination. Cite file and line.
4. **Frontend:** `cd frontend && npm run build` and report bundle sizes; flag a main chunk over 300 kB gzip.

## Output
A table of check, budget, measured value, verdict, plus file:line citations for any query concern. Synthetic data only; never log PII.
