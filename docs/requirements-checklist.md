# project.txt requirement checklist (verified 2026-10-01)

Status: MET, FIXED (was missing, implemented and verified), PARTIAL, NOT MET.

## 5. Acceptance criteria and NFRs
| Requirement | Status | Evidence |
|---|---|---|
| AC-01 to AC-10 implemented | MET | live API checks, 21/21 live Playwright, `specs/reviews/eval-all-groups.md`; 177/177 features pass |
| Every AC has a test referencing its AC-NN id | MET | grep of `AC-01`..`AC-10` over `backend/tests`, `frontend/tests`, `e2e/*.ts`: at least 3 backend files per AC |
| NFR-01 to NFR-08 | MET | tests tagged `NFR-0n` (3 to 21 files each); `tests/architecture/*` |

## 7.1 Claude Code specs
| Requirement | Status | Evidence |
|---|---|---|
| `specs/app_spec.md` plus per-feature specs with AC sections | MET | 8 feature specs plus app_spec, each with `AC-nn` sections (7 to 32 ids per file) |
| Layered CLAUDE.md, AGENTS.md as TOC | MET | root, `backend/`, `frontend/`, `tests/`, and `domain/`, `services/`, `repositories/`, `controllers/`; AGENTS.md is 21 lines |
| At least 3 project skills | MET | risk-classifier, watchlist-matcher, state-machine-validator, audit-tracer, archtest-author |
| At least 2 custom commands | MET | `ac-trace`, `pii-scan`, `sprint-report` |
| At least 2 project hooks | MET | `pii-redaction-check`, `rules-immutability-check`, `role-boundary-check`, wired in `.claude/settings.json` |
| At least 3 project agents | MET | kyc-orchestrator, screening, classifier, compliance-review, archtest-author |
| Agent SDK use in `scripts/` | MET | `scripts/agent_review.py` imports `claude_agent_sdk` and calls `query()` |
| Own `plugin.json` | MET | `plugin.json` (skills, commands, agents, hooks, mcp) |
| Debugging log / post-mortem in `docs/` | MET | `docs/debugging-log.md` (environment-first), `docs/fix-loops/001-*.md` |
| Playwright MCP in `.mcp.json`, used by evaluator | PARTIAL | `.mcp.json` configures `@playwright/mcp`; `evaluator` agent lists the Playwright MCP tools. In this session the MCP server failed to connect, so live UI evaluation used the Playwright test runner (`e2e/live/`). No review file shows MCP-driven evaluation. |

## 7.2 Business understanding
| Requirement | Status | Evidence |
|---|---|---|
| `docs/business-case.md` (problem, users, metrics, rules, value) | MET | sections Problem, Target users, Value proposition, Success metrics, Domain rules |
| At least 4 domain rule/validator files | MET | `backend/src/onboardx/domain/` has 17 modules (lifecycle, risk, matching, classifier, decision, validation, ...) |
| Frontend with a responsive layout | MET | 360 px and 1280 px overflow checks pass live (F072); mobile snapshot |
| AC in testable form for at least 4 specs | MET | AC-nn ids in all 8 feature specs |

## 7.3 Architectural discipline
| Requirement | Status | Evidence |
|---|---|---|
| `tests/architecture/` with at least 3 structural tests | MET | `test_layering.py`, `test_import_linter.py`, `test_no_float_scan.py`, `test_size_limits.py` |
| import-linter configured | MET | 5 contracts kept (`lint-imports`) |
| `docs/tdd.md` and at least 10 test files across history showing red-green | PARTIAL | `docs/tdd.md` exists with the AC-06 worked example; 70 test files. History has only 6 `test:`-prefixed commits, so red-then-green is thinly visible in git. History cannot be rewritten. |

## 7.4 Technical implementation
| Requirement | Status | Evidence |
|---|---|---|
| `docs/architecture.md` with diagram and layers | MET | 4 Mermaid blocks, layered structure, sequence diagrams |
| At least 3000 lines of generated code | MET | about 10,600 lines in `backend/src` and `frontend/src` |
| Playwright UI validation with snapshot directory | MET | `e2e/__screenshots__/` |
| At least 20 unit tests with coverage artefact and tool declared | MET | `backend/coverage.xml`; `pytest-cov` pinned in `requirements.lock`; backend 97.8%, frontend 96.8% |

## 7.5 CI/CD
| Requirement | Status | Evidence |
|---|---|---|
| CI file with build and test | FIXED | `.gitlab-ci.yml` existed; the GitHub remote had only a review workflow, so `.github/workflows/ci.yml` (backend, frontend, e2e) was added. The same commands pass locally; it has not run on GitHub yet. |
| Claude Code Action in CI | MET | `.github/workflows/claude.yml` (`anthropics/claude-code-action@v1`), `claude-review` job in `.gitlab-ci.yml` |
| At least 3 PR-driven merges, zero direct commits to main | PARTIAL | 10 merge commits. `git log --first-parent --no-merges main` shows 2 direct commits (`chore: initial empty commit`, `chore: ignore vite cache`). Published history, not rewritten. |

## 8.1 Mandatory deliverables
| Requirement | Status | Evidence |
|---|---|---|
| Working app, single command, seed data, README quick start | FIXED | was two terminals; added `python scripts/start_all.py` and a README quick start. Verified: `/health` 200, frontend 200, seeded login through the proxy. |
| Specs, CLAUDE.md hierarchy, agent substrate, plugin manifest, `.mcp.json` | MET | see 7.1 |
| Harness sprint cycle with contracts and evaluator output | MET | `sprint-contracts/` (6 files), `specs/reviews/` |
| Test suite incl. classification, AML, transitions, roles, override audit, architecture, Playwright, coverage | MET | backend 1318 passed; 113 frontend; 16 mocked + 21 live e2e |
| PR-driven history | PARTIAL | see 7.5 |

## 8.2 Good to have
| Requirement | Status | Evidence |
|---|---|---|
| Architecture doc diagram, `docs/tdd.md` worked example | MET | |
| Autonomous fix loop in `docs/fix-loops/` | MET | `001-upload-content-validation.md` (detect, reproduce, root cause, fix, validate, merge) |
| `docs/knowledge-deposits.md` | MET | |
| Multiple sprint cycles | MET | sprint contracts 2 to 5 plus group A and UI groups |
| Bonus agents | FIXED | added `performance-auditor` and `doc-writer` (registered in `plugin.json`) |

## 6. Functional scope
| Requirement | Status | Evidence |
|---|---|---|
| Reports incl. dropped-lead analysis | FIXED | API existed but no UI; dashboard now has a Dropped leads panel (AC-10.11 added to `specs/reports_spec.md`), verified live (21/21) and in unit and mocked e2e tests |
| Admin: manage classification rules and watchlist | MET | rule-set draft/publish and watchlist add/deactivate UI |
| Admin: manage product document checklists | FIXED | `specs/admin-management_spec.md` AC-12: admin Checklists page and `/api/v1/admin/checklists` append a new immutable version (old cases keep theirs); pytest and live Playwright pass. Supersedes the earlier v1 exclusion in `app_spec.md`. |
| Admin: user / role configuration | FIXED | AC-11: admin Users page and `/api/v1/admin/users` (create, change role, deactivate, reactivate); staff tokens honoured only for an active user with the stored role; audited; pytest and live Playwright pass |
| Analyst: manage queries | FIXED | AC-13: analysts raise and close queries, the owning prospect replies on the status page; append-only, PII-safe; pytest and live Playwright pass |

## Authentication and RBAC (added requirement)
| Requirement | Status | Evidence |
|---|---|---|
| NFR-04 authentication boundary at the controller layer; four roles | MET | `controllers/dependencies/auth.py` only; `test_role_matrix.py` covers every route for all four roles and anonymous |
| Login page | MET | unified `/login` for customers and staff, redirect by role |
| Sign-up page | FIXED | `/signup` and `POST /api/v1/auth/signup` create prospect accounts only (AC-14); staff accounts come from the admin Users page (AC-11) |
| Role-based access in the UI | MET | route guards (`RequireRole`), 403 page, live Playwright journey customer -> officer -> customer |
| Sign-up asks the account type (prospect, KYC analyst, compliance officer, admin) | FIXED | staff roles are created pending and need admin approval (AC-14.2, AC-14.8 to AC-14.10); self-assigned admin access is impossible |
| Who approves a case (auto vs compliance officer) | FIXED | `REVIEW_POLICY=auto` (default, the brief's AC-07) or `manual` (compliance officer approves every case, AC-15); `start_all.py --review-policy manual` |
| Admin sign-up without approval | FIXED (opt-in) | `ADMIN_SIGNUP=open` (`start_all.py --admin-signup open`) makes an admin sign-up active at once; default stays `approval` because open admin sign-up is a privilege-escalation risk (AC-14.11); analyst and officer always need approval |
