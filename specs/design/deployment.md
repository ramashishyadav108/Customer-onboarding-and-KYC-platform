# OnboardX Deployment

Status: DRAFT for `/design` approval. Scope is **local verification mode** per `project-manifest.json` (`deployment.method = local`). Production deployment, secrets management and multi-region are out of scope (BRD section 5); where a production concern is mentioned it is marked "later".

## 1. Environments

| Env | Purpose | Backend | Frontend | Database | Notes |
|---|---|---|---|---|---|
| dev | Day-to-day work and agent builds | `uvicorn` on :8000 inside `backend/.venv` | `vite` dev server on :3000, proxy `/api` to :8000 | PostgreSQL local instance (`onboardx_dev`) or SQLite file when none is installed | `.env` copied from `.env.example` by `init.sh` |
| test | pytest, vitest, Playwright | In-process `TestClient` or uvicorn started by the evaluator | `vite preview` or dev server | SQLite in-memory (backend tests) and SQLite file (E2E) with all migrations applied | Clock injected; synthetic fixtures in `tests/fixtures` |
| staging | Not provisioned in v1 | later | later | later | Would mirror prod settings with PostgreSQL |
| prod | Not in scope | later | later | later | Listed so the settings names are stable |

`health_check`: `GET http://localhost:8000/health`, 5 retries with 2 s backoff (manifest); the app must answer within 1 s of start.

## 2. Backend environment (venv)

```
cd backend
python -m venv .venv
.venv\Scripts\activate           (PowerShell: .venv\Scripts\Activate.ps1; Git Bash: source .venv/Scripts/activate)
pip install -r requirements.lock
pip install -e ".[dev]"
alembic upgrade head
python scripts/run_backend.py    (migration guard, then uvicorn --port 8000)
```

- `requirements.lock` is produced with `pip-compile` from `pyproject.toml` and committed; `pip install -r` gives reproducible installs.
- The venv is git-ignored. `init.sh` creates it when missing (replacing the current `uv sync` line; see `system-design.md` DD-15).
- Frontend: `cd frontend && npm ci && npm run dev` (port 3000).

## 3. Configuration (typed Settings, environment variables)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | yes | none (startup fails naming it) | `postgresql+psycopg://onboardx:onboardx@localhost:5432/onboardx` or `sqlite:///./onboardx.db` |
| `JWT_SECRET` | yes outside tests | none | HS256 signing key (synthetic dev value in `.env.example`) |
| `ACCESS_TOKEN_TTL_SECONDS` | no | 1800 | Token expiry (E1-S2) |
| `UPLOAD_DIR` | no | `../uploads` | Document storage root |
| `MAX_UPLOAD_BYTES` | no | 5242880 | 5 MB limit |
| `AUTO_ADVANCE_ON_SUBMIT` | no | false | Run the pipeline right after submit (DD-13) |
| `CORS_ALLOWED_ORIGINS` | no | `http://localhost:3000` | Frontend origin |
| `LOG_LEVEL` | no | INFO | |

## 4. CI/CD pipeline

Hosted CI is not part of the brief; the pipeline below is what the harness (`/build`, `/auto`, `/evaluate`) and any GitHub Actions workflow run, in this order. PR-only merges to `main`; conventional commits.

| Step | Command | Gate |
|---|---|---|
| 1 Install | `python -m venv backend/.venv && pip install -r requirements.lock && pip install -e ".[dev]"`; `npm ci` | exit 0 |
| 2 Migration guard | `pytest backend/tests/unit/test_migration_guard.py` (hash compare with `manifest.json`) | fails if an applied migration is edited or removed |
| 3 Lint and types | `ruff check .`, `mypy src/`, `npm run lint`, `npm run typecheck` | zero errors |
| 4 Layering | `lint-imports` plus `pytest backend/tests/architecture` | zero violations |
| 5 Backend tests | `pytest --cov=onboardx --cov-fail-under=80` (SQLite) | coverage >= 80 (ratchet) |
| 6 Frontend tests | `npm test -- --coverage` (vitest, vitest-axe) | coverage >= 80, zero serious/critical axe |
| 7 Start stack | `alembic upgrade head`, start backend :8000 and frontend :3000, poll `/health` | healthy in <= 10 s |
| 8 E2E and evaluation | Playwright specs in `e2e/` at 360 and 1280 px; sprint-contract API checks | contract criteria pass |
| 9 Security | `security-reviewer` agent plus `pip-audit` and `npm audit --audit-level=high` | no high findings |

## 5. Infrastructure as code

Local mode needs no cloud IaC. The reproducible definitions are: `pyproject.toml` and `requirements.lock` (backend), `package.json` and lockfile (frontend), Alembic migrations (schema and seed data), `.env.example` (configuration), `init.sh` (bootstrap). `/deploy` may later generate a Docker Compose stack from these without changing application code; no Dockerfile is required for verification.

## 6. Secrets management

No real secrets exist (synthetic data, no external integrations). `JWT_SECRET` and seeded synthetic passwords live in `.env.example` and the seed migration and are labelled dev-only. `.env` is git-ignored and protected by the `protect-env` hook; the `detect-secrets` hook scans commits. Passwords in the database are salted hashes. A production secrets store is out of scope (later).

## 7. Data, backups and seeds

- Schema and reference data come only from migrations `0001` to `0007`; demo data from `backend/scripts/seed_demo_cohort.py` (deterministic, 200 cases).
- Dev database reset: drop and recreate the database (or delete the SQLite file), then `alembic upgrade head`. Never edit a migration to reset state.
- Uploaded files live in `uploads/` (git-ignored) and are synthetic.

## 8. Rollback procedure

| Situation | Action |
|---|---|
| Bad application change | Revert the PR on `main` (git revert), rerun steps 1 to 8; no data change required |
| Bad migration not yet applied elsewhere | Fix forward with a new migration. Do not edit the merged file (the guard fails) |
| Bad migration applied in dev | Drop and recreate the dev database, apply the fixed sequence. Forward-only migrations are the policy (append-only, NFR-05); `alembic downgrade` is not relied on |
| Wrong published rule set | Publish a new version (published versions are immutable); existing assessments keep their version; use reclassification with an audit record for affected cases |
| Wrong watchlist entry | Deactivate (appends a row); never delete |
| Stack will not start | Check `/health`, read JSON logs by `correlation_id`, confirm `DATABASE_URL` and migration guard output |
