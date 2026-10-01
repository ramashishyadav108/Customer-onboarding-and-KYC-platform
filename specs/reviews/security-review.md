# Security Review - OnboardX - 2026-10-01

Scope: backend/src/onboardx (FastAPI), backend/migrations, frontend/src (React), dependency manifests.
Method: static read of auth, routers, upload path, report SQL, logging, migrations, frontend storage; live probes against http://127.0.0.1:8010 (throwaway instance; created a handful of synthetic leads/documents only).
Context: all data is synthetic and this is a capstone. Items marked ACCEPTABLE-BY-SCOPE would be BLOCK in production.

## Summary
- BLOCK findings: 0 (for capstone scope). 2 items would be BLOCK in production (VULN-001, VULN-002).
- WARN findings: 6
- INFO findings: 8
- Overall verdict: WARN

Positive results (verified): no SQL injection, no IDOR on case_id routes, no auth bypass, no XSS sink, no path traversal, no secrets committed.

## WARN Findings

### [VULN-001] No rate limiting / lockout on login or public lead endpoint
Files: backend/src/onboardx/controllers/routers/auth.py (login), controllers/routers/leads.py (POST /leads)
Severity: WARN (production: BLOCK). ACCEPTABLE-BY-SCOPE.
Probe: 30 consecutive bad logins for admin1 all returned 401 with no throttling or delay. Seed passwords are documented in migration 0003 docstring (lines 3-8), so credential guessing is moot, but unlimited attempts are possible. POST /leads is unauthenticated and mints a token plus a case each call, so unbounded case/row creation is possible.
Fix: add per-IP and per-username throttling (e.g. slowapi or a reverse-proxy limit), exponential backoff or temporary lockout, and a cap on leads per IP/time window.

### [VULN-002] Known demo credentials seeded by migration, active in every environment
File: backend/migrations/versions/0003_seed_users.py lines 3-8 (docstring) and 25-50 (users)
Severity: WARN (production: BLOCK). ACCEPTABLE-BY-SCOPE (explicitly documented synthetic).
Probe: analyst1 / demo-analyst1-pass logged in successfully on the live instance. Admin, officer, analyst and prospect1 accounts all use predictable passwords.
Fix: seed users only when an explicit dev flag is set, or read initial passwords from environment variables and force rotation on first login; never run this migration in a production profile.

### [VULN-003] Upload content is not sniffed; stored bytes can differ from declared type
Files: backend/src/onboardx/domain/documents.py lines 36-45 (validate_upload); services/document_service.py lines 174-175, 223; controllers/routers/documents.py line 40
Severity: WARN
Probe: an HTML file with a script tag, sent as filename pan.png and content-type image/png, was accepted (201) and stored as {case_id}/{uuid}.png. Validation trusts the client-supplied Content-Type and the filename extension only; no magic-byte check (PDF "%PDF-", PNG signature, JPEG SOI).
Mitigations present: storage path is server-generated (case_id/uuid.ext), the client filename is never used on disk (confirmed: a filename with traversal sequences was sanitised and stored safely), extension is derived from the validated MIME, 5 MiB cap enforced with a limit+1 read (413 confirmed), and there is currently no download endpoint, so stored-XSS or content-confusion is not reachable today.
Fix: verify magic bytes against the declared type before saving; if a download/preview endpoint is added, serve with Content-Type from the DB, X-Content-Type-Options: nosniff, and Content-Disposition: attachment.

### [VULN-004] Upload size limit is enforced after the multipart body is already received
File: backend/src/onboardx/controllers/routers/documents.py line 40
Severity: WARN. ACCEPTABLE-BY-SCOPE.
Description: file.read(limit+1) caps what is read into memory, but Starlette's multipart parser spools the whole request body (to a temp file) before the handler runs, so a very large upload still consumes disk and bandwidth. A prospect token is trivially obtainable (public /leads), so this is reachable unauthenticated in effect. No global request-body limit exists on any route.
Fix: enforce a Content-Length / streaming body cap in middleware or at the reverse proxy (e.g. 6 MiB for the upload route, 64 KiB for JSON routes).

### [VULN-005] Missing security headers and no CORS policy
File: backend/src/onboardx/main.py lines 74-89; frontend/index.html
Severity: WARN
Probe: responses to /health and API calls carry no Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy or HSTS. No CORSMiddleware is installed (an OPTIONS preflight from a foreign origin gets 405 with no Access-Control headers), which is the safe default: the Vite proxy makes the SPA same-origin.
Fix: add a small ASGI middleware (or proxy config) setting CSP default-src 'self', X-Content-Type-Options nosniff, X-Frame-Options DENY, Referrer-Policy no-referrer, Cache-Control no-store on API responses. If a separate frontend origin is ever used, add CORSMiddleware with an explicit origin allowlist (never "*" with credentials).

### [VULN-006] Frontend dependency vulnerabilities (npm audit) and loose version ranges
File: frontend/package.json (lines 14-34 caret ranges); frontend/package-lock.json
Severity: WARN (dev-tooling items) / INFO (runtime item)
npm audit: 8 findings (2 critical, 1 high, 5 moderate).
- vitest <=4.1.10 (critical: Vitest UI server arbitrary file read/exec), @vitest/coverage-v8 (critical via vitest), vite <=6.4.2 (high: path traversal in optimized-deps .map handling), esbuild <=0.24.2 (moderate: any website can query the dev server). All are dev-server/test tooling only, not shipped in dist; exposure exists only while `vite`/`vitest --ui` listens locally.
- react-router/react-router-dom 6.30.6 (moderate: open redirect via backslash in Link/useNavigate; SSR-hydration issue). The app does not use SSR, and navigate()/Link targets are built from the ROUTES constants rather than user input, so this is not reachable today. The fix requires a major upgrade to 7.x.
Fix: bump vite/vitest/coverage-v8 to the fixed major versions; plan a react-router v7 upgrade; do not run the dev server or vitest UI bound to non-loopback interfaces. package.json uses caret ranges; the lockfile pins actual versions, so commit and use `npm ci` in CI.

## INFO Findings

### [VULN-007] JWT secret falls back to an ephemeral random value; HS256 shared secret; no iss/aud/jti
Files: backend/src/onboardx/main.py lines 61-66; config/settings.py line 24; services/auth_service.py lines 14, 70-96
Severity: INFO
Assessment of JWT handling (good): algorithm is pinned (algorithms=["HS256"], alg:none token rejected with 401 on the live instance); exp, sub, role are required; expiry compared against the injected clock; role parsed via the Role enum so unknown roles fail; TTL is 30 minutes by default and gt=0 validated; secret comes from env (JWT_SECRET) and is not in source; a missing secret yields a random per-process secret with a warning rather than a hardcoded default (safe, but means tokens die on restart and multi-worker deployments would reject each other's tokens).
Weaknesses: no minimum length / entropy check on JWT_SECRET (.env.example uses "dev-only-not-a-secret"); the same secret is also used as the HMAC key for the idempotency fingerprint (lead_service.py line 141), mixing key purposes; no iss/aud claims; no revocation/refresh (logout is client-side only; a stolen token is valid up to 30 minutes).
Fix: require len(JWT_SECRET) >= 32 when set (and refuse to start with the example value outside dev); derive a separate key for fingerprints; add iss/aud; consider a token denylist only if revocation matters.

### [VULN-008] Idempotency-Key replay returns a fresh token for an existing case
Files: backend/src/onboardx/services/lead_service.py lines 62-71, 141-150, 213-220; controllers/routers/leads.py
Severity: INFO. ACCEPTABLE-BY-SCOPE.
Description: replaying POST /leads with the same Idempotency-Key and an identical name/contact/product re-issues a valid case-bound prospect token (created=False, HTTP 200). Anyone who knows the key and the PII payload (name and contact are guessable) can obtain access to that prospect's case. The key namespace is global (scope "leads"), not bound to a client.
Fix: bind keys to the caller (IP/session) or return the original response without minting a new token; use high-entropy keys only.

### [VULN-009] Prospect token is a bearer capability issued without any identity proof
Files: controllers/routers/leads.py; services/lead_service.py line 213
Severity: INFO. ACCEPTABLE-BY-SCOPE (design decision DD-6).
Description: possession of the token is the only proof of case ownership. Tokens are bound to exactly one case: require_case_access / require_case_owner (controllers/dependencies/auth.py lines 55-78) compare the token's case_id claim with the path case_id. Live probe: prospect A's token against prospect B's case returned 403; prospect token against /cases, /admin/reports and unauthenticated /evidence returned 403/403/401.
Note: if the user must re-enter later (token lost), there is no recovery path, which is a functional rather than a security issue.

### [VULN-010] Access control review (routes) - no defects found
Files: backend/src/onboardx/controllers/routers/*.py, dependencies/auth.py
Severity: INFO (positive)
Every router declares a role dependency; public routes are only /health, POST /leads, POST /auth/login (and FastAPI /docs, /openapi.json). Admin routers use router-level or per-route require_role(ADMIN); review/override/reclassify require COMPLIANCE_OFFICER; reject-document requires KYC_ANALYST; screen/classify/decide/advance require KYC_ANALYST or ADMIN; per-case routes use require_case_access (owner or any staff) or require_case_owner (submit, upload, profile, notifications). Superseded documents are blocked for prospects. No ownership gap was found for case_id routes; document_id is checked against case_id in documents.reject (`stored.case_id != case_id` -> 404).
Observation: staff access is not scoped per case (any staff role sees any case), which is consistent with the spec for a shared work queue. /docs and /openapi.json are exposed unauthenticated; disable in non-dev (FastAPI(docs_url=None, openapi_url=None)).

### [VULN-011] SQL injection review of report_queries.py - no defect
File: backend/src/onboardx/repositories/report_queries.py lines 17-85, 106-107
Severity: INFO (positive)
All SQL is static string constants executed via sqlalchemy text() with named bind parameters (:product, :start, :stop, :cutoff, :limit); no f-string or concatenation of user input into SQL. Filter inputs are typed upstream (Product enum, date objects, int ge/le bounds). The only dynamic parts are ISO date strings built from parsed date objects. The queries select no PII columns. The SQLite-specific strftime would need replacement if the DB changes, which is not a security matter.

### [VULN-012] PII handling in logs, responses and errors (NFR-03) - largely sound
Files: backend/src/onboardx/config/redaction.py, logging_setup.py, controllers/middleware.py, controllers/error_handlers.py
Severity: INFO
Good: logs are structured JSON with a redaction filter (email, phone, PAN, Aadhaar, income, occupation, key-based) applied both as handler filter and formatter; the request log records only method, path (contains case_id UUID), status and duration (no query string or body); the unhandled-error handler logs only the exception type; the 5xx envelope is generic; validation errors return field names and messages only (no echoed input); services log case_id only; audit payloads store field names rather than values; contact is masked in case detail (contact_masked), though note the mask is "last 2 chars" so email "a@b.com" shows "*****om". Prospect name is returned in clear to the owner and staff (name only).
Weaknesses: (1) middleware logs the raw correlation ID header (validated against a safe regex and 64-char style limit, so no log injection); (2) the Authorization header is never logged, good; (3) redaction is regex-based best effort, new fields containing PII under non-listed keys (e.g. "name") are not key-redacted; currently nothing logs them. Add "name" and "comment" to PII_KEYS defensively.
Also: the notification stub and audit trail may store the comment free text (override/reject comments up to 500 chars); treat as potentially sensitive.

### [VULN-013] Password hashing - acceptable
Files: backend/src/onboardx/services/passwords.py lines 7-30; migrations/versions/0003_seed_users.py
Severity: INFO
PBKDF2-HMAC-SHA256, 210,000 iterations, 16-byte random per-user salt, constant-time compare via hmac.compare_digest, malformed stored hash fails closed, unknown-user timing is equalised with a dummy hash at the same iteration count. 210k is below the current OWASP guidance for PBKDF2-HMAC-SHA256 (600,000 iterations, 2023+), but the iteration count is stored per hash so it can be raised. verify_password trusts the iteration count in the stored hash (DoS only if the DB is already compromised). Seed hashes in migration 0003 use the same 210k parameters and per-user salts (not reused). Login input is length-capped (username 100, password 200), which limits hashing DoS.
Fix: raise DEFAULT_ITERATIONS to 600,000 (or move to argon2id/scrypt) and rehash on successful login when the stored iteration count is lower than the default.

### [VULN-014] Secrets in repo / environment hygiene
Files: .env (untracked), .env.example, .gitignore, backend/tests, .github/workflows/claude.yml
Severity: INFO
`.env` is git-ignored and not tracked (git ls-files lists only .env.example and frontend/.env.example); .env contains a synthetic 64-hex JWT_SECRET with an in-memory SQLite URL and should still not be shared or reused. .env.example holds only the placeholder "dev-only-not-a-secret". Test files contain demo passwords/fixture secrets (S105/S106 ruff exceptions for tests/**), INFO as fixtures. The GitHub workflow uses secrets.ANTHROPIC_API_KEY from the secret store (no literal). Uploaded files live in ../uploads (git-ignored, untracked in history by the "stop tracking runtime upload directory" commit; check earlier history for any committed uploads or .eval.db if the repo is ever made public: `.eval.db` and `.eval_server.log` exist in the working tree and are covered by the `.eval*` ignore rule).
Also: backend/requirements.lock is fully pinned (pip-compile), including dev tools in the same lock; versions look current. pip-audit is not installed in the venv, so Python CVE results were not obtained (see fixes).

### [VULN-015] Frontend token storage and XSS
Files: frontend/src/state/AuthContext.tsx lines 22, 33-34; api/client.ts lines 26-40
Severity: INFO
Token and role are stored in sessionStorage (key onboardx.session), mirrored in an in-memory variable. This survives reload within the tab but is readable by any script on the origin, so an XSS bug would expose it; sessionStorage is tab-scoped and cleared on close, which is better than localStorage. A grep for dangerouslySetInnerHTML, innerHTML, eval and document.write across frontend/src found no matches, and React escapes all rendered values, so no XSS sink exists. The 401 handler signs the user out. Role gating in RequireRole is UX only; the server enforces roles (verified above), which is the correct design.
Fix (optional): keep the token in memory only (accept re-login on reload), or move to an httpOnly SameSite=Strict cookie plus CSRF protection; add the CSP from VULN-005 as defence in depth.
CSRF: not applicable today because auth is via an Authorization bearer header, not cookies.

## Acceptable-by-scope summary (capstone, synthetic data)
VULN-001 (rate limiting), VULN-002 (seeded demo credentials), VULN-004 (body size at proxy), VULN-008 (idempotency replay token), VULN-009 (DD-6 bearer prospect token), SQLite database, in-process stub notifications, no TLS in dev.

## Prioritised fixes
1. Add magic-byte validation for uploads and keep any future download endpoint attachment-only with nosniff (VULN-003).
2. Add rate limiting/lockout for /auth/login and /leads, and a request-body size limit (VULN-001, VULN-004).
3. Gate the demo-user seed behind a dev flag / env-provided passwords before any non-demo deployment (VULN-002).
4. Add security headers middleware (CSP, nosniff, frame deny, no-store) and disable /docs and /openapi.json outside dev (VULN-005, VULN-010).
5. Enforce JWT_SECRET minimum length and refuse the example value; use a separate key for idempotency fingerprints; consider iss/aud (VULN-007).
6. Raise PBKDF2 iterations to 600k with rehash-on-login (VULN-013).
7. Update frontend dev tooling (vite/vitest/coverage-v8) and plan react-router v7; run pip-audit against requirements.lock and add both audits to CI (VULN-006, VULN-014).
8. Bind idempotency replays so they do not mint new tokens (VULN-008).
9. Add "name" and "comment" to the redaction key set; optionally move the token to in-memory storage (VULN-012, VULN-015).
