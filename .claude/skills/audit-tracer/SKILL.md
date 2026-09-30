---
name: audit-tracer
description: Traces and verifies the append-only audit trail for decisions, overrides and documents (NFR-02, AC-08). Use when touching audit, decisions or overrides.
---

# audit-tracer

## Rules
- KYC document records, screening results, decisions and overrides are append-only (NFR-02): no UPDATE/DELETE in repositories; DB triggers enforce it (migration 0002).
- An override (AC-08) records case_id, actor, previous and new decision, reason code and timestamp. A band reassignment also requires an override record (NFR-08).
- Logs carry case_id and a correlation id, never plaintext PII (NFR-03, NFR-06).

## Trace procedure
1. Pick a case_id; list state history, screening results, decisions and overrides in order.
2. Verify every state change has a history row and every override has an actor and reason code.
3. Verify no code path issues UPDATE/DELETE on append-only tables (`grep -rn "UPDATE\|DELETE" backend/src/repositories`).
4. Write findings to `specs/reviews/audit-trace-<case>.md`.
