# OnboardX

Customer onboarding and KYC platform. FastAPI + SQLAlchemy + Alembic (SQLite) backend, React + TypeScript + Vite frontend. All data is synthetic.

```
backend/    Python 3.12 API (src/onboardx, migrations, tests)
frontend/   React app (Vite dev server on :3000, proxies /api to :8000)
e2e/        Playwright specs (backend mocked with page.route)
specs/      Requirements, design and API contracts (the spec wins over code)
```

## Prerequisites

- Python 3.12
- Node.js 18 or newer and npm
- Git Bash or PowerShell on Windows (commands below show both where they differ)

## 1. Run the backend (port 8000)

First-time setup, from the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e ".[dev]"
```

Git Bash: activate with `source .venv/Scripts/activate` instead. Linux/macOS: `source .venv/bin/activate`.

Configure and start (still in `backend/`):

```powershell
$env:DATABASE_URL = "sqlite:///./onboardx.db"
$env:JWT_SECRET   = "dev-only-not-a-secret-change-me-0123456789"
$env:UPLOAD_DIR   = "../uploads"
python scripts/run_backend.py
```

Git Bash equivalent: `export DATABASE_URL=sqlite:///./onboardx.db JWT_SECRET=... UPLOAD_DIR=../uploads`.

`scripts/run_backend.py` verifies the migration guard, applies every Alembic migration (schema plus seed data) and starts uvicorn on `http://127.0.0.1:8000`. Check it:

```
curl http://localhost:8000/health        # {"status":"ok"}
```

Interactive API docs: `http://localhost:8000/docs`.

### Backend settings (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | none, required | e.g. `sqlite:///./onboardx.db` (use a file; `sqlite://` is in-memory and lost on exit) |
| `JWT_SECRET` | random per start | HS256 signing key; set it so tokens survive restarts |
| `TOKEN_TTL_SECONDS` | 1800 | access token lifetime |
| `UPLOAD_DIR` | `../uploads` | where uploaded KYC documents are stored |
| `AUTO_ADVANCE_ON_SUBMIT` | `true` | submit runs screening, classification and the decision synchronously |
| `LOG_LEVEL` | `INFO` | JSON logs with correlation id and case_id, never plaintext PII |
| `BACKEND_HOST`, `BACKEND_PORT` | `127.0.0.1`, `8000` | bind address |

You can also put these in a git-ignored `.env` file in the repository root (see `.env.example`).

### Seeded demo users (synthetic, dev only)

| Username | Password | Role |
|---|---|---|
| `prospect1` | `demo-prospect1-pass` | prospect |
| `analyst1` | `demo-analyst1-pass` | kyc-analyst |
| `officer1` | `demo-officer1-pass` | compliance-officer |
| `admin1` | `demo-admin1-pass` | admin |

Log in with `POST /api/v1/auth/login`. Prospects are normally created by `POST /api/v1/leads`, which returns a case-bound token.

### Try the pipeline from the command line

```bash
# 1. register a lead (returns case_id and a prospect token)
curl -s -X POST localhost:8000/api/v1/leads -H "Content-Type: application/json" \
  -d '{"name":"Test Person Alpha","contact":"9999999921","product":"Savings"}'
# 2. PUT /api/v1/cases/{id}/profile, 3. POST /api/v1/cases/{id}/documents (multipart:
#    checklist_item + file named pan_*.pdf, utility-bill_*.pdf, photograph_*.jpg),
# 4. POST /api/v1/cases/{id}/submit
```

With `AUTO_ADVANCE_ON_SUBMIT=true` the case goes straight to `APPROVED` (clean, low risk) or `MANUAL_REVIEW`. With it `false`, staff drive the steps: `POST /api/v1/cases/{id}/screen`, `/classify`, `/decide`, or all at once with `/advance`. Document classification is a stub decided by file-name prefix (`pan_`, `aadhaar_`, `passport_`, `utility-bill_`, `photograph_`, `gst-certificate_`, `visa_`).

### Seed the 200-case demo cohort

With the backend configured as above (stop it first if it is running), from `backend/`:

```powershell
python scripts/seed_demo_cohort.py          # deterministic: fixed seed, synthetic names only
```

It drives the real services to create 200 cases (about 67 percent auto-approved, the rest held for or resolved by manual review), so the admin reports show data. Run it once on a fresh database; it refuses a non-empty one unless you pass `--force`. Then log in as `admin1` and call `GET /api/v1/admin/reports/auto-approval`, `/tat`, `/funnel`, `/backlog`, `/time-per-stage`, `/rejection-reasons` or `/dropped-leads`.

### Manual review, admin and reports (API)

| Endpoint | Role |
|---|---|
| `GET /api/v1/review-queue`, `POST /api/v1/cases/{id}/override`, `POST /api/v1/cases/{id}/reclassify` | compliance-officer (`officer1`) |
| `GET /api/v1/cases/{id}/evidence`, `GET /api/v1/cases/{id}/account` | staff (the account also for the owning prospect, masked) |
| `/api/v1/admin/rule-sets`, `/api/v1/admin/watchlist`, `/api/v1/admin/reports/*` | admin (`admin1`) |

Full interactive docs: `http://localhost:8000/docs`.

### Backend checks

```powershell
cd backend
python -m pytest -q --cov=onboardx --cov-report=xml     # full suite with coverage
python -m ruff check .                                   # lint
python -m mypy src                                       # types
lint-imports                                             # layering contracts (import-linter)
```

Migrations 0001 to 0007 are append-only: never edit them. A schema change is a new migration, then `python scripts/update_migration_manifest.py`.

## 2. Run the frontend (port 3000)

In a second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. The dev server proxies `/api` and `/health` to `http://localhost:8000`, so start the backend first. To point at a different backend: `VITE_BACKEND_URL=http://host:port npm run dev`.

### Frontend checks

```bash
npm run lint          # eslint
npm run typecheck     # tsc --noEmit
npm test              # vitest with coverage
npm run build         # type-check and production build into dist/
npm run preview       # serve the build on :3000
```

### End-to-end tests (Playwright)

```bash
cd e2e
npm ci
npx playwright install     # first time only: downloads browsers
npm test                   # runs against the frontend with the API mocked
```

## 3. Run everything

Two terminals:

| Terminal | Commands |
|---|---|
| 1 (backend) | `cd backend`, activate the venv, set `DATABASE_URL` and `JWT_SECRET`, `python scripts/run_backend.py` |
| 2 (frontend) | `cd frontend`, `npm run dev` |

Then browse to `http://localhost:3000`. `init.sh` (Git Bash) installs the backend and frontend dependencies in one go.

## Troubleshooting

- `Invalid configuration: DATABASE_URL` on start: set `DATABASE_URL` (see above).
- `401 UNAUTHENTICATED` after a restart: set a fixed `JWT_SECRET`; with none, a new random key is generated each start and old tokens stop working.
- Port 3000 or 8000 already in use: stop the other process, or set `BACKEND_PORT`; the frontend port is fixed to 3000 (`strictPort`).
- Reset local data: stop the backend, delete `backend/onboardx.db` and the `uploads/` folder, start again (migrations re-seed users, checklists, rules and the watchlist).
