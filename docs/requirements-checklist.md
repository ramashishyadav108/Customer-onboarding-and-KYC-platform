# project.txt requirement checklist

Re-verified from the repository on 2026-10-02. Status: **MET**, **PARTIAL** (works but the evidence is thinner than the brief asks), **NOT MET**. Numbers below were measured, not assumed.

## Summary
| Section | Items | MET | PARTIAL | NOT MET |
|---|---|---|---|---|
| 5.1 Functional ACs | 10 | 10 | 0 | 0 |
| 5.2 NFRs | 8 | 8 | 0 | 0 |
| 6 Functional scope | 11 | 11 | 0 | 0 |
| 7.1 Specs and AI-native substrate | 10 | 9 | 1 | 0 |
| 7.2 Business understanding | 4 | 4 | 0 | 0 |
| 7.3 Architectural discipline | 3 | 2 | 1 | 0 |
| 7.4 Technical implementation | 5 | 5 | 0 | 0 |
| 7.5 CI/CD | 3 | 2 | 1 | 0 |
| 8.1 Mandatory deliverables | 10 | 8 | 2 | 0 |
| 8.2 Good to have | 5 | 5 | 0 | 0 |

The PARTIAL items come from three causes: the git history cannot be rewritten (2 early direct commits on `main`, a thin red-then-green commit pattern); Playwright MCP is configured but no review file shows an MCP-driven evaluation; and the GitHub workflow has not run on a remote yet.

## 5.1 Functional acceptance criteria
| AC | Status | Evidence |
|---|---|---|
| AC-01 lead registration, INITIATED, case_id | MET | lead API and form; cited in 15 test files; live Playwright |
| AC-02 checklist upload, missing documents block submit | MET | 20 test files; live F070 |
| AC-03 stubbed classification, unrecognised flagged | MET | 9 files; live F071 |
| AC-04 lifecycle and `InvalidOnboardingStateException` | MET | full transition matrix (`test_lifecycle.py`), 5 files |
| AC-05 AML/PEP screening, hit to MANUAL_REVIEW | MET | 8 files; watchlist journey live |
| AC-06 versioned integer rule engine, immutable published versions | MET | 14 files; database triggers |
| AC-07 auto-approval and stub account | MET | 11 files; default `REVIEW_POLICY=auto` keeps it exactly |
| AC-08 officer override with reason code, audited | MET | 10 files; live officer journey |
| AC-09 notification per transition, re-upload without restart | MET | 14 files; in-place re-upload on the status page |
| AC-10 reports (TAT, funnel, backlog, time per stage, rejection reasons) | MET | 11 files; seven dashboard panels including dropped leads |

Every acceptance-criterion id in the specs is cited by a test: 16 of 16 top-level ids and 137 of 137 detailed ids (`AC-nn.m`) across the ten specs.

## 5.2 Non-functional requirements
| NFR | Status | Evidence |
|---|---|---|
| NFR-01 integer-only scoring | MET | `test_no_float_scan.py` AST scan; 10 files |
| NFR-02 append-only documents, screening, decisions, overrides | MET | database triggers (migrations 0002, 0008, 0009); 13 files |
| NFR-03 no plaintext PII in logs | MET | log-capture tests incl. queries, sign-up and file views; 19 files |
| NFR-04 auth at the controller layer, four roles | MET | `controllers/dependencies/auth.py` only; role matrix covers every route for all roles; 33 files |
| NFR-05 append-only migrations | MET | migration guard and manifest; 8 files |
| NFR-06 JSON logs with correlation id and case_id | MET | 5 files |
| NFR-07 health within 1 second | MET | subprocess startup test |
| NFR-08 architecture rules as tests | MET | published rules immutable, locked cases, reclassification audit; 12 files |

## 6 Functional scope
| Item | Status | Evidence |
|---|---|---|
| Register lead | MET | |
| Upload documents with classification feedback | MET | |
| Track status incl. queries, decisions, reason codes | MET | status timeline, notifications, analyst queries (AC-13) |
| Re-upload | MET | |
| Account activation message | MET | |
| KYC analyst workbench: review documents, VERIFIED/REJECTED with reason, manage queries | MET | workbench, reject with reason, queries; analysts open the uploaded files (AC-16) |
| Compliance officer queue | MET | queue, review panel, override; documents viewable (AC-16) |
| Screening engine with rule reference and timestamp | MET | |
| Risk classification engine | MET | |
| Admin console: checklists, rules, watchlist, users and roles | MET | Users (with staff approval), Checklists, Rule sets, Watchlist pages (AC-11, AC-12, AC-14) |
| Reports incl. dropped-lead analysis | MET | |

## 7.1 Specs and AI-native substrate
| Requirement | Status | Evidence |
|---|---|---|
| `specs/app_spec.md` plus per-feature specs with AC sections | MET | 10 spec files: app_spec, the 8 named feature specs, `admin-management_spec.md` |
| Layered CLAUDE.md, AGENTS.md as TOC | MET | 8 CLAUDE.md files (root, backend, frontend, tests, domain, services, repositories, controllers); AGENTS.md 21 lines |
| At least 3 project skills | MET | risk-classifier, watchlist-matcher, state-machine-validator, audit-tracer, archtest-author |
| At least 2 project commands | MET | ac-trace, pii-scan, sprint-report |
| At least 2 project hooks | MET | pii-redaction-check, rules-immutability-check, role-boundary-check (wired in settings) |
| At least 3 project agents | MET | kyc-orchestrator, screening, classifier, compliance-review, archtest-author (plus 2 bonus) |
| Agent SDK in `scripts/` | MET | `scripts/agent_review.py` (`claude_agent_sdk.query`) |
| Own `plugin.json` | MET | skills, commands, agents, hooks, mcp |
| Debugging log or post-mortem in `docs/` | MET | `docs/debugging-log.md`, `docs/fix-loops/001-*.md` |
| Playwright MCP in `.mcp.json`, used by the evaluator | PARTIAL | `.mcp.json` configures `@playwright/mcp`. The evaluator and design-critic agents listed only the plugin's tool names (`mcp__plugin_playwright_playwright__*`), which do not match the project's own server (`mcp__playwright__*`); both name forms are now listed. The MCP server failed to connect in the authoring session, so no review file shows an MCP-driven evaluation; live UI checks used the Playwright test runner (`e2e/live`). |

## 7.2 Business understanding
| Requirement | Status | Evidence |
|---|---|---|
| `docs/business-case.md` (problem, users, metrics, rules, value) | MET | all five sections present |
| At least 4 domain rule files | MET | 20 modules in `backend/src/onboardx/domain/` |
| Responsive frontend | MET | 360 px and 1280 px overflow checks (live), mobile snapshots |
| AC in testable form for at least 4 specs | MET | AC-NN ids in all 10 specs |

## 7.3 Architectural discipline
| Requirement | Status | Evidence |
|---|---|---|
| Architecture tests, at least 3 | MET | layering, import-linter, no-float, size limits, account-stub-no-network |
| import-linter enforcing layering | MET | 5 contracts kept |
| `docs/tdd.md` and at least 10 test files showing red-green-refactor | PARTIAL | `docs/tdd.md` with the AC-06 worked example; 77 test files. Git shows only 6 `test:` commits, so red-then-green is thinly visible. History is published and was not rewritten. |

## 7.4 Technical implementation
| Requirement | Status | Evidence |
|---|---|---|
| `docs/architecture.md` with diagram and layers | MET | 4 Mermaid blocks, layered structure, sequence diagrams |
| At least 3000 lines of generated code | MET | about 12,800 lines in `backend/src` and `frontend/src` |
| Playwright UI validation with snapshot directory | MET | `e2e/__screenshots__/` (10 images), mocked and live suites |
| Tests tagged with AC ids, every spec AC covered | MET | see 5.1 |
| At least 20 unit tests with a coverage artefact and tool declared | MET | `backend/coverage.xml`; `pytest-cov` pinned; backend 98%, frontend 97% |

## 7.5 CI/CD
| Requirement | Status | Evidence |
|---|---|---|
| CI file with build and test | MET | `.gitlab-ci.yml` (backend, frontend, e2e jobs). By choice it creates no pipeline on push or merge request; run it on purpose with `RUN_PIPELINE=true`. |
| Claude Code Action | MET | `.github/workflows/claude.yml` (`anthropics/claude-code-action@v1`, manual trigger only by choice), `claude-review` job in GitLab CI |
| At least 3 PR-driven merges, zero direct commits to main | PARTIAL | 10 merge commits. `git log --first-parent --no-merges main` shows 2 direct commits (`chore: initial empty commit`, `chore: ignore vite cache`). Published history, not rewritten. |

## 8.1 Mandatory deliverables
| Deliverable | Status | Evidence |
|---|---|---|
| 1 Working app, single command, seed data, README quick start | MET | `python scripts/start_all.py` (seeds checklists, rules, watchlist, demo users); README quick start |
| 2 `docs/business-case.md` | MET | |
| 3 Specs: lead-capture, document-checklist, document-classification-stub, screening, classification, manual-review, account-creation-stub, reports | MET | all eight exist with AC sections |
| 4 Layered CLAUDE.md | MET | |
| 5 Agent substrate | MET | |
| 6 Harness sprint cycle with contracts and reviews | MET | 9 contract files in `sprint-contracts/`, 7 files in `specs/reviews/` |
| 7 Plugin manifest and `.mcp.json` | PARTIAL | both files exist; the evidence of MCP use is the PARTIAL in 7.1 |
| 8 Test suite: classification branches, AML matching, state transitions, role boundaries, override audit, architecture, AC-tagged, Playwright, coverage | MET | every category present and committed |
| 9 CI pipeline with Claude Code Action, passing build on main | PARTIAL | pipelines exist and every command passes locally; a passing run on the remote cannot be shown until the workflow runs there (nothing pushed since it was added) |
| 10 PR-driven history | MET | merges via `--no-ff`; see 7.5 for the 2 early direct commits |

## 8.2 Good to have
| Item | Status | Evidence |
|---|---|---|
| 11 Architecture and TDD docs | MET | sequence diagrams; AC-06 worked example |
| 12 Autonomous fix loop in `docs/fix-loops/` | MET | detect, reproduce, root cause, fix, validate, merge |
| 13 `docs/knowledge-deposits.md` | MET | |
| 14 Multiple sprint cycles | MET | sprints 1 to 5 plus admin management, accounts, staff sign-up and review policy |
| 15 Bonus agents | MET | performance-auditor, doc-writer |

## Beyond the brief (added on request)
Prospect sign-up and unified sign-in with role redirects; staff sign-up needing admin approval (admin sign-up optional via `ADMIN_SIGNUP=open`); configurable review policy (`REVIEW_POLICY`); analyst queries; admin user and checklist management; staff can open uploaded documents (AC-16). Specs: `specs/admin-management_spec.md`.
