# Knowledge deposits

Recurring mistakes encoded back into rules, hooks and skills.

| Mistake | Encoded as |
|---------|------------|
| Logging PII in plaintext | `.claude/hooks/pii-redaction-check.js`, `backend/src/onboardx/config/redaction.py`, test `test_pipeline_logging` |
| Mutating a published rule set or append-only row | `.claude/hooks/rules-immutability-check.js`, DB triggers (migration 0002), `risk-classifier` and `audit-tracer` skills |
| Business or auth logic in the wrong layer | `.claude/hooks/role-boundary-check.js`, import-linter contracts, `tests/architecture/` |
| Floats in scoring | `tests/architecture/test_no_float_scan.py`, `risk-classifier` skill |
| Timing a startup requirement from process spawn | `docs/debugging-log.md`: NFR-07 test measures from first accepted connection |
| Assuming a tool (`uv`) exists | `docs/debugging-log.md`: check the environment before choosing commands |
| Dev proxy using `localhost` (resolves to IPv6 `::1` on Node 18) while the API binds IPv4 | `frontend/vite.config.ts` targets `127.0.0.1` |
