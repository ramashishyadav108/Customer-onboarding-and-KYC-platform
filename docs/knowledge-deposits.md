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
| Trusting client-declared upload type (Content-Type / extension) | Magic-byte validation in `domain/documents.py` (`validate_content`) + tests `test_upload_content_validation.py`, `test_upload_signatures.py` (docs/fix-loops/001) |

## Staff tokens are checked against the user store

- **Mistake:** a signed staff token was trusted for its whole lifetime, so a deactivated or demoted user kept their old authority, and a test minted a staff token for a user that did not exist.
- **Rule now:** `AuthService.verify_token` resolves staff authority from the stored user (active, current role) on every request (AC-11.4, AC-11.5). Tests must log in as a seeded user instead of forging staff tokens; `test_role_matrix.py` covers every route for all four roles.

## In-memory SQLite needs serialised units of work

- **Mistake:** concurrent reads on the shared in-memory connection returned half-read rows (500 on the evidence endpoint).
- **Rule now:** `make_uow_factory(serialize=True)` for in-memory engines, guarded by `tests/integration/test_in_memory_concurrency.py`.
