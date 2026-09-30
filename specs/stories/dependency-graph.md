# Dependency Graph

Groups are computed as 1 + the longest dependency chain. Stories inside a group are independently executable in parallel. No circular dependencies (validated by script before writing).

## Group A

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E1-S1 | Platform exposes health, structured logs, typed config and migration guard | Config | - |
| E1-S4 | Onboarding state machine enforces the lifecycle and audits every transition | Service | - |
| E1-S5 | Document checklist is defined per product and versioned | Config | - |
| E3-S2 | Risk rule sets are versioned with integer weights and immutable once published | Repository | - |

## Group B

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E1-S2 | User can authenticate with a token and is restricted by role | API | E1-S1 |
| E2-S3 | Stub classifier returns canned results for known fixture files | Service | E1-S1 |
| E4-S2 | Account creation is stubbed on approval | Service | E1-S4 |
| E5-S1 | Turnaround and per-stage duration metrics are computed from history | Service | E1-S4 |

## Group C

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E1-S3 | Prospect can register a lead and receive a case ID | API | E1-S2, E1-S4, E1-S5 |

## Group D

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E2-S1 | Prospect can upload KYC documents against checklist items | API | E1-S3, E2-S3 |

## Group E

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E2-S2 | Missing documents or profile block case submission | API | E2-S1, E1-S4 |
| E2-S4 | Prospect can re-upload missing or rejected documents without restarting | API | E2-S1, E2-S3 |

## Group F

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E2-S5 | Prospect portal lets the applicant register, upload and track status | UI | E2-S2, E2-S4, E1-S3 |
| E3-S1 | Case name is screened against the static AML/PEP watchlist | Service | E2-S2, E1-S4 |
| E4-S4 | Stubbed notifications fire at each lifecycle transition | Service | E1-S4, E2-S4 |

## Group G

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E3-S3 | Cases are classified LOW, MEDIUM or HIGH risk by the versioned rule engine | Service | E3-S1, E3-S2 |
| E3-S4 | Admin can manage rule sets and the watchlist through the API | API | E3-S1, E3-S2, E1-S2 |

## Group H

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E3-S5 | Staff can review case evidence and manage rules in the staff UI | UI | E3-S3, E3-S4, E2-S4 |
| E4-S1 | Low-risk clean cases are auto-approved and all others routed to manual review | Service | E3-S3, E4-S2 |

## Group I

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E4-S3 | Compliance officer can override manual review with an audited reason | API | E4-S1, E4-S2, E1-S2 |

## Group J

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E4-S5 | Compliance review queue and portal notifications are available in the UI | UI | E4-S3, E4-S4, E4-S1, E2-S5 |
| E5-S2 | Funnel, manual-review backlog, auto-approval and rejection-reason metrics are computed | Service | E4-S1, E4-S3 |
| E5-S5 | Architecture and compliance rules are enforced as automated tests | Service | E3-S2, E4-S1, E4-S3 |

## Group K

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E5-S3 | Admin reports API serves all admin metrics | API | E5-S1, E5-S2, E1-S2 |

## Group L

| Story | Title | Layer | Depends on |
|---|---|---|---|
| E5-S4 | Admin console dashboard shows operational reports | UI | E5-S3, E3-S5 |
