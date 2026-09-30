# OnboardX Folder Structure

Status: DRAFT for `/design` approval. This tree and `component-map.md` are the routing instructions for `/build`: builder agents create files only at these paths.

Backend dependency management: **a standard Python virtual environment** (`python -m venv backend/.venv`), per user instruction. Dependencies are declared in `backend/pyproject.toml` and installed with `pip install -e ".[dev]"` inside the venv; `backend/requirements.lock` (pip-compile output, committed) pins exact versions. This replaces the `uv` commands in `project-manifest.json`, `init.sh` and `CLAUDE.md`, which `/build` must update (see `system-design.md` section 9).

## 1. Repository tree

```
capstone4/
  backend/                               Python 3.12 FastAPI service (own venv)
    .venv/                               Virtual environment (git-ignored, created by init.sh)
    pyproject.toml                       Dependencies, ruff, mypy, pytest, coverage, import-linter contracts
    requirements.lock                    Pinned dependency versions (pip-compile), committed
    alembic.ini                          Alembic config (script_location = migrations)
    migrations/                          Append-only schema and seed migrations (NFR-05)
      env.py                             Alembic environment; reads DATABASE_URL from Settings
      manifest.json                      SHA-256 of every migration file; guard compares against it
      versions/                          One file per migration, never edited after merge
        0001_core_schema.py              Tables, FKs, indexes, CHECK constraints
        0002_append_only_triggers.py     UPDATE/DELETE triggers (PostgreSQL + SQLite variants), rule-set and case-lock triggers
        0003_seed_users.py               Four synthetic users with salted password hashes
        0004_seed_checklists_v1.py       Savings, Current, NRE checklist v1
        0005_seed_classification_rules_v1.py  Filename-prefix classifier rules v1
        0006_seed_rule_set_v1.py         Published risk rule set v1
        0007_seed_watchlist_v1.py        10 synthetic watchlist entries (5 AML, 5 PEP)
    scripts/                             Operational scripts (not imported by the app)
      update_migration_manifest.py       Adds hashes for NEW migration files only; refuses to change existing ones
      seed_demo_cohort.py                Deterministic 200-case synthetic cohort (AC-10.6, demo)
      run_backend.py                     Starts uvicorn on :8000 after migration guard and `alembic upgrade head`
    src/onboardx/                        Application package (import root `onboardx`)
      main.py                            Composition root: create_app(), wires settings, middleware, routers (exempt from layering, imports everything)
      domain/                            LAYER 1 (lowest). Pure Python: no I/O, no frameworks, no DB
        enums.py                         Product, CaseState, Role, DocClass, DocStatus, RiskBand, reason-code enums
        lifecycle.py                     Frozen transition table (AC-04) and is_terminal()
        errors.py                        InvalidOnboardingStateException, CaseLockedError, PublishedRuleSetImmutableError, domain ValidationError, etc.
        entities.py                      Frozen dataclasses for Case, Document, ScreeningResult, RiskAssessment, Decision, Override, Account, Notification
        risk.py                          RuleSet value objects (integer-only validation), band_for_score(), publish-validity rules
        matching.py                      normalise_name(), token_key(): NFKC, lowercase, punctuation strip, sorted tokens
        masking.py                       mask_contact(), mask_account_number()
        account_numbers.py               derive_account_number(case_id, product) (SHA-256 derived)
        ports.py                         Protocols: Clock, NotificationSender, FileStore, TransitionObserver
      config/                            LAYER 2. May import domain only
        settings.py                      Typed Settings (pydantic-settings) from env; fails naming DATABASE_URL when unset
        logging_setup.py                 JSON log formatter, correlation_id and case_id context vars
        redaction.py                     PII redaction filter (PAN, Aadhaar, phone, email, income, occupation)
        constants.py                     Upload limits, allowed extensions, reason-code lists, token TTL default
        migration_guard.py               Compares migration file hashes to manifest.json (NFR-05)
      repositories/                      LAYER 3. SQLAlchemy and file storage; may import domain and config
        database.py                      Engine and session factory (PostgreSQL / SQLite), SQLite PRAGMA foreign_keys
        unit_of_work.py                  Transaction boundary exposing all repositories
        models/                          SQLAlchemy ORM models (persistence only)
          base.py                        Declarative base, naming convention, UUID and timestamp types
          identity.py                    User
          cases.py                       Case, CaseProfile, ChecklistTemplate, ChecklistItem, StateHistory
          documents.py                   Document, DocumentRejection, ClassificationRule, ClassificationResult
          screening.py                   ScreeningResult, WatchlistEntry, WatchlistDeactivation
          risk.py                        RiskRuleSet, RiskAssessment
          decisions.py                   Decision, Override, Account
          messaging.py                   Notification
          audit.py                       AuditLog, IdempotencyKey
        user_repository.py               Lookup by username
        case_repository.py               Create, get, list (filters, pagination), update state (only callable by transition service)
        profile_repository.py            Get and upsert profile while INITIATED
        checklist_repository.py          Read-only checklist templates and items
        state_history_repository.py      add() and read only (no update or delete methods)
        audit_repository.py              add() and read only
        document_repository.py           add() version, current-per-item, list, add rejection (no update or delete)
        classification_repository.py     Rules read, results add and read
        screening_repository.py          Results add and latest; watchlist entries and deactivations add and read; watchlist_version
        rule_set_repository.py           Drafts insert and update (DRAFT only), publish, read versions
        risk_assessment_repository.py    add() and latest (no update or delete)
        decision_repository.py           Decisions and overrides add and read
        account_repository.py            add() and get by case (no update or delete)
        notification_repository.py       add() and list newest first
        idempotency_repository.py        Insert and lookup
        report_queries.py                Read-only aggregate SQL over state_history, decisions, overrides
        file_store.py                    Local filesystem FileStore implementation, traversal-safe paths
      services/                          LAYER 4. Business rules; may import domain, config, repositories. Never FastAPI, SQLAlchemy or controllers
        onboarding_service.py            The single transition function: validate, update state, history row, audit, observer hook, idempotency
        audit_service.py                 Builds PII-free audit entries
        auth_service.py                  Login, password verification, JWT issue and verify (verification function used by the controller dependency)
        lead_service.py                  Create lead (idempotent), update profile, masked case read
        case_view_service.py             Assembles CaseDetail, workbench list and evidence view
        checklist_service.py             Checklist lookup and version pinning
        classifier_service.py            Stub classifier (prefix rules, mismatch check), no content read
        document_service.py              Upload, re-upload versioning, list, reject, status derivation, action_required
        submission_service.py            Submit with MISSING_DOCUMENTS and MISSING_PROFILE checks
        screening_service.py             Watchlist matching, result persistence, SCREENED transition
        risk_service.py                  Integer scoring engine, classify, reclassify (audit record required)
        rule_set_service.py              Draft, edit, publish, validity checks, immutability
        watchlist_service.py             Add and deactivate entries (append-only), audit
        decision_service.py              Decide, reason-code precedence, account creation in same transaction
        account_service.py               create_account() idempotent stub
        override_service.py              Review queue and override with audited reason
        notification_service.py          TransitionObserver implementation, DOC_REJECTED, stub sender call after commit
        pipeline_service.py              advance(): screen, classify, decide, idempotent
        reports/                         Metric services (integers only)
          filters.py                     ReportFilters validation (product, from, to)
          tat.py                         TAT by product
          time_per_stage.py              Average seconds per from-state
          funnel.py                      Approval funnel with conversion_bp
          backlog.py                     Manual-review backlog and buckets
          rejection_reasons.py           Top five reasons
          auto_approval.py               Rate in bp vs 6000 target
      controllers/                       LAYER 5 (highest in backend). FastAPI; may import everything below
        dependencies/
          auth.py                        Bearer decode, require_roles(), require_case_access() (NFR-04: only place auth is enforced)
          services.py                    Builds services per request from Settings and UnitOfWork
        schemas/                         Pydantic request and response models (StrictInt for every rule field)
          common.py                      Error envelope, enums, ReportFilters
          auth.py                        Login
          cases.py                       Lead, profile, CaseDetail, list, evidence
          documents.py                   Upload response, reject
          pipeline.py                    Screen, classify, decide, advance responses
          review.py                      Queue, override, reclassify, notifications
          admin.py                       RuleSet, watchlist
          reports.py                     Report payloads
        routers/                         One router per resource group, thin: parse, call service, map result
          health.py                      GET /health
          auth.py                        POST /api/v1/auth/login
          leads.py                       POST /api/v1/leads
          cases.py                       GET /cases, GET /cases/{id}, PUT profile, GET evidence
          products.py                    GET /products/{product}/checklist
          documents.py                   Upload, list, reject, submit
          pipeline.py                    screen, classify, decide, advance
          review.py                      review-queue, override, reclassify
          notifications.py               GET /cases/{id}/notifications
          admin_rule_sets.py             Rule-set CRUD and publish
          admin_watchlist.py             Watchlist add, list, deactivate
          admin_reports.py               Six report endpoints
        error_handlers.py                Maps domain errors to the error envelope and HTTP codes
        middleware.py                    Correlation ID, request logging (no bodies)
    tests/                               Backend tests (pytest); SQLite in-memory for unit and integration
      conftest.py                        App factory, SQLite engine with migrations applied, fixed Clock, token helpers
      unit/                              Pure domain and service tests with fake repositories
      integration/                       API tests with TestClient against migrated SQLite
      property/                          Hypothesis property tests (score range, matching)
      architecture/                      E5-S5 rule tests (append-only, locked case, layering, PII logs, no floats)
  frontend/                              React 18 + TypeScript + Vite (port 3000)
    package.json                         Scripts: dev, build, test, lint, typecheck
    vite.config.ts                       Dev server :3000, proxy /api to :8000
    tsconfig.json                        strict true, noImplicitAny
    eslint.config.js                     Includes import/no-restricted-paths zones enforcing frontend layering
    index.html
    src/
      main.tsx                           App bootstrap
      types/                             FRONTEND LAYER 1: API types mirroring api-contracts (hand-maintained from schema), enums
      config/                            LAYER 2: API base URL, route constants, reason-code option lists
      api/                               LAYER 3: typed fetch client (token, correlation id, error envelope) and one module per resource
        client.ts                        Fetch wrapper, error mapping to ApiError
        auth.ts  leads.ts  cases.ts  documents.ts  pipeline.ts  review.ts  notifications.ts  adminRuleSets.ts  adminWatchlist.ts  adminReports.ts
      state/                             LAYER 4: auth context, token storage (sessionStorage), role guards
        AuthContext.tsx                  Holds token, role, case_id
        RequireRole.tsx                  Route guard, redirects to /forbidden
      hooks/                             LAYER 4: data hooks (useCase, useChecklistUpload, useReviewQueue, useReports) over api/
      components/                        LAYER 5: reusable accessible UI
        StatusChip.tsx  FormField.tsx  ReasonSelect.tsx  ConfirmDialog.tsx (focus trap, Escape)  DataTable.tsx  ChartWithTable.tsx  EmptyState.tsx  AppShell.tsx  SkipLink.tsx
      pages/                             LAYER 6 (highest): route pages, no fetch calls, use hooks
        prospect/                        LeadFormPage, ProfilePage, UploadPage, StatusPage
        staff/                           LoginPage, WorkbenchPage, CaseDetailPage, ReviewQueuePage, ReviewPanel
        admin/                           DashboardPage, RuleSetsPage, WatchlistPage
        ForbiddenPage.tsx
      styles/                            Design tokens (CSS variables) and base styles, WCAG AA contrast-checked
    tests/                               Vitest + Testing Library + vitest-axe (axe-core), one file per page or component
  e2e/                                   Playwright end-to-end specs (happy path, manual review, re-upload, a11y sweeps, responsive 360 and 1280)
  tests/
    fixtures/
      documents/                         Synthetic files named per classifier convention (pan_valid.pdf, aadhaar_valid.jpg, passport_valid.png, utility-bill_valid.pdf, photograph_valid.png, gst-certificate_valid.pdf, visa_valid.pdf, unknown_scan.pdf, bad_type.exe, oversize_6mb.pdf)
      cohort/                            Expected-values JSON for the 50-case metrics fixture and 1,000-case latency fixture generator config
  specs/                                 BRD, stories, features.json, design artifacts (this directory)
  docs/
    architecture.md                      Layer rules and Mermaid diagrams, copied from specs/design/system-design.md sections 3 to 6 by /build
  uploads/                               Local upload storage root (git-ignored)
  project-manifest.json  features.json  init.sh  claude-progress.txt  CLAUDE.md
```

## 2. import-linter configuration (goes in `backend/pyproject.toml`)

```toml
[tool.importlinter]
root_package = "onboardx"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Backend layers flow one way: controllers > services > repositories > config > domain"
type = "layers"
layers = [
  "onboardx.controllers",
  "onboardx.services",
  "onboardx.repositories",
  "onboardx.config",
  "onboardx.domain",
]

[[tool.importlinter.contracts]]
name = "Domain is pure (no frameworks, no persistence, no I/O libraries)"
type = "forbidden"
source_modules = ["onboardx.domain"]
forbidden_modules = ["sqlalchemy", "fastapi", "starlette", "pydantic", "alembic", "jwt", "httpx", "requests"]

[[tool.importlinter.contracts]]
name = "Services and config do not touch web or ORM frameworks"
type = "forbidden"
source_modules = ["onboardx.services", "onboardx.config"]
forbidden_modules = ["fastapi", "starlette", "sqlalchemy", "alembic"]
# config/settings.py uses pydantic-settings, which is permitted (not listed).

[[tool.importlinter.contracts]]
name = "Only repositories use SQLAlchemy"
type = "forbidden"
source_modules = ["onboardx.domain", "onboardx.config", "onboardx.services", "onboardx.controllers"]
forbidden_modules = ["sqlalchemy"]
# controllers/dependencies/services.py obtains sessions through onboardx.repositories.unit_of_work, never sqlalchemy directly.

[[tool.importlinter.contracts]]
name = "Service-level ordering: orchestration above steps above leaf services"
type = "layers"
layers = [
  "onboardx.services.pipeline_service",
  "onboardx.services.decision_service | onboardx.services.override_service",
  "onboardx.services.screening_service | onboardx.services.risk_service | onboardx.services.submission_service | onboardx.services.document_service | onboardx.services.lead_service | onboardx.services.case_view_service | onboardx.services.rule_set_service | onboardx.services.watchlist_service",
  "onboardx.services.onboarding_service | onboardx.services.account_service | onboardx.services.notification_service | onboardx.services.classifier_service | onboardx.services.checklist_service | onboardx.services.auth_service",
  "onboardx.services.audit_service",
]
```

Notes for builders:
- `onboardx.main` is deliberately not in any layer (composition root).
- `notification_service` implements `domain.ports.TransitionObserver`; `onboarding_service` depends only on the port, so there is no service-to-service cycle.
- `decision_service` and `override_service` call `account_service` (lower) and `onboarding_service` (lower). `pipeline_service` calls screening, risk and decision services (all lower).
- The contract run is `lint-imports` (command in `system-design.md` section 6) and is part of `pytest` through `tests/architecture/test_layering.py` (which also runs the AST scan required by E5-S5 AC4 without depending on the tool).
- `report_queries.py` (repositories) returns plain integers and tuples; no float, Decimal or `avg()` SQL (integer division is done in Python or with `//` on integer sums).

## 3. Frontend layering (ESLint `import/no-restricted-paths`)

Order low to high: `types` < `config` < `api` < `state` < `hooks` < `components` < `pages`. A file may import only from layers to its left; `pages` never imports `api` directly (only hooks). Zones in `frontend/eslint.config.js` mirror the backend rule; violations fail `npm run lint`.

## 4. Naming and size conventions

Python modules `snake_case.py`; classes `PascalCase`; React components `PascalCase.tsx`; hooks `useX.ts`. Functions under 50 lines, files under 300 lines (hook-enforced). Migration files are numbered `NNNN_description.py` and are never edited after merge; changes go in a new file, followed by `scripts/update_migration_manifest.py`.
