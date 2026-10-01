# Evaluation: Group A (E1-S1, E1-S4, E1-S5, E3-S2)

Target: http://127.0.0.1:8010 (contract says :8000; overridden by caller). Date 2026-10-01.
Verdict: PASS for all four stories. No failures, so no eval-failures-NNN.json written.

## API checks (live, curl)
- A-API-01 GET /health: PASS. 200, body {"status":"ok"}.
- A-API-02 GET /health with X-Correlation-ID abc-123: PASS. 200, response header x-correlation-id: abc-123.
- A-API-03 GET /health without header: PASS. Header present (e.g. 4b2afa8a-a8df-43a2-8f28-403a90a7c848, cf6dc618-e65e-4cb9-a842-f78463990326); both have version nibble 4.
- A-API-04 GET /api/v1/products/Savings/checklist, no auth: PASS. 401, {"error":{"code":"UNAUTHENTICATED","message":"Authentication required","details":{}}}.
- Perf /health: 5 calls, 5-7 ms each (limit 1000 ms): PASS.
- Extra (login exists in this build; analyst1 token): Savings 200 v1 items ID_PROOF[PAN,AADHAAR,PASSPORT], ADDRESS_PROOF[AADHAAR,PASSPORT,UTILITY_BILL], PHOTOGRAPH[PHOTOGRAPH] all mandatory (F036/F039). Current 200 = Savings + mandatory BUSINESS_PROOF[GST_CERTIFICATE] (F037). NRE 200 ID_PROOF[PASSPORT], OVERSEAS_ADDRESS_PROOF[VISA] mandatory (F038). Loan 404 {"error":{"code":"NOT_FOUND",...}} (F040).

## Pytest / architecture / typing (run in backend/)
- Requested AC-tagged selection (-m "ac or nfr" -k "AC_04 or AC_06 or lifecycle or risk"): 173 passed, 1125 deselected.
- Full suite (pytest -q --no-cov): 1297 passed, 1 skipped (tests/unit/test_file_store.py:55, symlinks not permitted on Windows; not a group-A feature). Includes all group-A named files.
- tests/architecture: 304 passed (includes test_no_float_in_risk.py, layering).
- ruff check .: All checks passed. mypy src/: no issues in 106 files.
- frontend `npx tsc --noEmit`: clean (no output).

## Not run / limitations
- Coverage gate (--cov-fail-under=80) not run; --no-cov used.
- frontend `npm run build`/`npm install` under Node 18, init.sh, migration alembic-on-empty-DB and file-existence checks were not independently executed by me; migration guard/trigger/seed behaviour is covered by passing pytest (F008/F009/F034/F042/F089/F092) only.
- F002 (startup <=1000 ms) proven only by the pytest subprocess test, not live.
- Playwright layer: no playwright_checks in contract. Covered by committed e2e suite, see e2e/ and e2e/__screenshots__/ (14 mocked-API tests, all passing in the last run). NOT live-verified by me.
- Log-content features (F003-F006) proven by pytest only; I did not read server logs.

## Frontend dev-server error reported mid-run
User pasted vite errors "Failed to resolve import @/config / @/state/AuthContext". Read-only diagnosis: src/config/index.ts and src/state/AuthContext.tsx exist (mtime 08:02:14), vite.config.ts alias '@' -> ./src and tsconfig paths exist (mtime 08:02:14), tsc --noEmit is clean, and nothing is listening on 3000/5173 now. Errors timestamped 08:05 so most likely a stale dev server holding a pre-08:02 module graph; restart `npm run dev`. I made no source edits (evaluator scope).
