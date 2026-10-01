# OnboardX Data Models

Status: DRAFT for `/design` approval. Machine-readable twin: `data-models.schema.json` (JSON Schema draft-07, one definition per entity under `definitions`). Storage: PostgreSQL (runtime), SQLite (tests). SQLAlchemy 2.x models in `repositories/models/`; domain dataclasses/enums in `domain/` mirror them. Schema changes ship only as new Alembic migrations (NFR-05).

## 1. Cross-cutting rules

| Rule | Detail |
|---|---|
| Primary keys | UUID (stored as `uuid` on PostgreSQL, `CHAR(36)` on SQLite) for entities exposed in the API; `BIGINT GENERATED ALWAYS AS IDENTITY` surrogate `seq` on append-only tables to give a total order independent of clock resolution |
| Timestamps | UTC, `timestamptz` (PostgreSQL) / ISO text (SQLite). All set by the service layer through an injected `Clock` so tests and the synthetic cohort are deterministic |
| Numbers | Integers only. No `float`, `real`, `double`, `numeric(p,s)` column anywhere. Ratios are basis points, durations seconds, money whole INR (NFR-01) |
| Append-only (NFR-02) | Tables marked **AO** have `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise an exception; repositories for them expose only `add` and read methods. Trigger DDL has a PostgreSQL and a SQLite variant in the same migration |
| Conditionally mutable | `cases` (state and `updated_at` only, via the transition service), `case_profiles` (only while case is INITIATED), `risk_rule_sets` (only while DRAFT; trigger blocks UPDATE/DELETE when `status = 'PUBLISHED'`) |
| PII | Direct PII: `cases.name`, `cases.contact`, `case_profiles.*`, `watchlist_entries.name/aliases`. Never logged (NFR-03); contact masked on read; reports never select these columns |
| Enums | Stored as `TEXT` with `CHECK (col IN (...))`, never DB enum types (simplifies append-only migrations and SQLite) |
| Foreign keys | Enforced (`PRAGMA foreign_keys=ON` in SQLite). `ON DELETE RESTRICT` everywhere (nothing is deleted) |

## 2. Entity overview

```
users (1)        (bound optional) -> cases
cases (1) -- (1) case_profiles
cases (n) -> (1) checklist_templates (1) -- (n) checklist_items
cases (1) -- (n) documents (1) -- (n) classification_results
documents (1) -- (n) document_rejections
classification_rules (seeded; referenced by rule_version)
cases (1) -- (n) state_history | audit_log | notifications | screening_results
cases (1) -- (n) risk_assessments (n) -> (1) risk_rule_sets
cases (1) -- (n) decisions | overrides ; cases (1) -- (0..1) accounts
watchlist_entries (1) -- (0..1) watchlist_deactivations
```

## 3. Entities

### 3.1 users (seeded by migration; mutable only by migration)
| Field | Type | Constraints | Notes |
|---|---|---|---|
| user_id | uuid | PK | |
| username | text | unique, not null | `prospect1`, `analyst1`, `officer1`, `admin1` |
| password_hash | text | not null | salted (argon2 or PBKDF2-HMAC-SHA256 with per-user salt); never returned or logged |
| role | text | CHECK in four roles | |
| case_id | uuid | null, FK cases | Bound case for a prospect user (DD-6); null for staff |
| created_at | timestamp | not null | |

Example: `{"user_id":"b1f0...","username":"analyst1","password_hash":"$argon2id$...","role":"kyc-analyst","case_id":null,"created_at":"2026-10-01T00:00:00Z"}`

### 3.2 cases
| Field | Type | Constraints | Notes |
|---|---|---|---|
| case_id | uuid | PK | |
| name | text | 1-100 chars, not null | PII |
| contact | text | not null | PII; 10-digit phone or email |
| product | text | CHECK Savings/Current/NRE | |
| state | text | CHECK 7 states, not null | changed only by `OnboardingService.transition` |
| checklist_version | integer | not null, FK checklist_templates | pinned at creation (AC-02.3) |
| created_at | timestamp | not null | |
| updated_at | timestamp | not null | |

Indexes: `(state, created_at)` (workbench and queue), `(product, created_at)` (reports), `(state)`.
DB guard: trigger rejects any UPDATE of `cases` when `OLD.state IN ('APPROVED','REJECTED')` (defence in depth for NFR-08; the service raises `CaseLockedError` first).
Example: `{"case_id":"3f0c...","name":"Test Person One","contact":"9999999921","product":"Savings","state":"INITIATED","checklist_version":1,"created_at":"2026-10-01T09:30:00Z","updated_at":"2026-10-01T09:30:00Z"}`

### 3.3 case_profiles (one row per case)
| Field | Type | Constraints |
|---|---|---|
| case_id | uuid | PK, FK cases |
| date_of_birth | date | not null |
| annual_income | bigint | not null, >= 0 (whole INR) |
| occupation_category | text | CHECK six categories |
| country_code | char(2) | `^[A-Z]{2}$` |
| state_code | char(2) | null; `^[A-Z]{2}$` when present; required by the profile API when `country_code` is IN (DD-14) |
| updated_at | timestamp | not null |

A trigger rejects UPDATE/DELETE unless the owning case is INITIATED.

### 3.4 checklist_templates and checklist_items (append-only, seeded by migration) **AO**
`checklist_templates`: `product` text, `version` int, PK `(product, version)`, `created_at`.
`checklist_items`: `product`, `version`, `item_code` (CHECK five codes), `mandatory` bool, `accepted_classes` (JSON array of DocClass), PK `(product, version, item_code)`, FK to template.
Seeded v1 per `specs/document-checklist_spec.md`. A new version is a new set of rows.
`cases.checklist_version` references `(product, version)` (composite FK on `(product, checklist_version)`).

### 3.5 documents **AO**
One row per uploaded file version. Nothing is updated; "superseded" is derived as "a higher `version` exists for the same `(case_id, checklist_item)`".
| Field | Type | Constraints |
|---|---|---|
| document_id | uuid | PK |
| seq | bigint identity | unique |
| case_id | uuid | FK cases, not null |
| checklist_item | text | CHECK five codes |
| version | integer | >= 1; unique `(case_id, checklist_item, version)` |
| storage_path | text | relative path under upload dir, `{case_id}/{document_id}.{ext}` (server generated) |
| display_name | text | sanitised original name, basename only, max 100 chars; never logged |
| content_type | text | `application/pdf`, `image/jpeg`, `image/png` |
| size_bytes | integer | 1..5242880 |
| sha256 | char(64) | hex |
| uploaded_by | text | actor id |
| uploaded_at | timestamp | not null |

Indexes: `(case_id, checklist_item, version DESC)`.

### 3.6 document_rejections **AO**
`rejection_id` uuid PK, `seq`, `document_id` FK, `case_id` FK, `reason_code` (CHECK five codes), `comment` text null, `actor`, `created_at`.
Current status of a document = REJECTED if a rejection row exists, else latest `classification_results.status`.

### 3.7 classification_rules (seeded, append-only) **AO**
`rule_version` int, `prefix` text (lowercase, e.g. `pan_`), `doc_class`, `status` (VERIFIED or FLAGGED), `confidence_bp` int, `priority` int, PK `(rule_version, prefix)`. The catch-all UNRECOGNISED behaviour is code, not a row. Seeded v1 per `specs/document-classification-stub_spec.md`.

### 3.8 classification_results **AO**
| Field | Type | Notes |
|---|---|---|
| result_id | uuid PK | |
| seq | bigint identity | |
| document_id | uuid FK | |
| doc_class | text | seven classes or UNRECOGNISED |
| status | text | VERIFIED or FLAGGED |
| reason_code | text null | DOC_UNRECOGNISED or DOC_CLASS_MISMATCH |
| confidence_bp | integer | 0..10000 |
| rule_version | integer | |
| classified_at | timestamp | |

### 3.9 screening_results **AO**
`id` uuid PK, `seq`, `case_id` FK, `hits` JSON array of `{entry_id, list_type, reason_code}`, `requires_manual_review` bool, `watchlist_version` int, `screened_at`. Index `(case_id, seq DESC)`.

### 3.10 watchlist_entries and watchlist_deactivations **AO**
`watchlist_entries`: `entry_id` uuid PK, `seq`, `name` text (PII-like, synthetic), `aliases` JSON array of text, `list_type` (AML or PEP), `name_tokens` text (normalised sorted token string, used for matching), `alias_tokens` JSON array, `added_by`, `created_at`. Seeded with 10 entries (5 AML, 5 PEP).
`watchlist_deactivations`: `id` uuid PK, `seq`, `entry_id` FK unique (one deactivation per entry), `deactivated_by`, `created_at`.
`watchlist_version` = number of rows in both tables (monotonic because nothing is deleted). Active at time T = entry created <= T and no deactivation <= T.

### 3.11 risk_rule_sets (mutable while DRAFT only)
| Field | Type | Constraints |
|---|---|---|
| version | integer | PK, >= 1 |
| status | text | DRAFT or PUBLISHED |
| weights | JSON | `{age, income_band, occupation_category, geography}` ints, sum 100 at publish |
| points | JSON | per factor tables, ints 0..100 |
| geography_map | JSON | country_code -> category |
| geography_default | text | category |
| border_states | JSON | array of state codes that map to DOMESTIC_BORDER when country_code is IN (DD-14); seeded v1 = `["JK","PB","AS"]` |
| low_max, medium_max | integer | `low_max < medium_max < 100` at publish |
| author | text | |
| created_at, published_at | timestamp | published_at null while DRAFT |

Triggers: UPDATE/DELETE rejected when `OLD.status = 'PUBLISHED'`; INSERT with `status='PUBLISHED'` allowed only in a migration (seed v1). Validation (integers only) happens in domain value objects before persistence; JSON numbers with a fractional part fail parsing in the controller schema (`StrictInt`).

### 3.12 risk_assessments **AO**
`assessment_id` uuid PK, `seq`, `case_id` FK, `score` int 0..100, `band` (LOW/MEDIUM/HIGH), `rule_version` int FK, `source` (RULE_ENGINE or OFFICER_RECLASSIFY), `breakdown` JSON array of `{factor, value_label, points, weight, contribution}`, `created_at`. Index `(case_id, seq DESC)`. "Current assessment" is the highest `seq` for the case.

### 3.13 decisions **AO**
`decision_id` uuid PK, `seq`, `case_id` FK **unique** (one automatic decision per case, which makes `decide` idempotent), `type` (AUTO), `outcome` (APPROVED or MANUAL_REVIEW), `reason_code` (AUTO_APPROVED, AML_HIT, PEP_HIT, DOC_UNRECOGNISED, RISK_MEDIUM, RISK_HIGH), `rule_version`, `actor`, `created_at`.

### 3.14 overrides **AO**
`override_id` uuid PK, `seq`, `case_id` FK **unique** (MANUAL_REVIEW is resolved once; the terminal states have no exits), `actor`, `previous_state` (always MANUAL_REVIEW), `decision` (APPROVE or REJECT), `reason_code` (seven codes), `comment` text null (max 500), `rule_version`, `created_at`.

### 3.15 accounts **AO**
`account_id` uuid PK, `case_id` FK **unique**, `product`, `account_number` text `^(SAV|CUR|NRE)[0-9]{12}$` unique, `created_at`. Derivation: prefix by product plus 12 decimal digits from `int(sha256(case_id).hexdigest(), 16) % 10**12` zero-padded.

### 3.16 notifications **AO**
`notification_id` uuid PK, `seq`, `case_id` FK, `event` (eight values), `template` text, `text` text (rendered, no contact), `details` JSON (`item_code`, `reason_code`), `contact_masked` text, `created_at`. Unique `(case_id, event)` except `DOC_REJECTED` (partial unique index `WHERE event <> 'DOC_REJECTED'`) to guarantee exactly one per state entered (AC-09.1).

### 3.17 state_history **AO**
`history_id` uuid PK, `seq`, `case_id` FK, `from_state` text null (null for the initial INITIATED row), `to_state`, `actor`, `reason_code` text null, `idempotency_key` text null, `created_at`. Unique `(case_id, to_state)` (each state is entered at most once, so a repeat cannot add a second row). Index `(case_id, seq)`, `(to_state, created_at)`.

### 3.18 audit_log **AO**
`audit_id` uuid PK, `seq`, `case_id` uuid null, `event` text, `actor` text, `role` text, `payload` JSON (PII-free), `correlation_id` text, `created_at`. Index `(case_id, seq)`, `(event, created_at)`.

### 3.19 idempotency_keys
`key` text, `scope` text (`leads` or `transition:{case_id}:{step}`), PK `(scope, key)`, `request_hash` char(64), `response` JSON, `created_at`. Insert-only (never updated); a replay reads it.

## 4. State lifecycle (for reference)

`INITIATED -> DOCS_SUBMITTED -> SCREENED -> CLASSIFIED -> {APPROVED | REJECTED | MANUAL_REVIEW}`, `MANUAL_REVIEW -> {APPROVED | REJECTED}`. The table lives in `domain/lifecycle.py` as a frozen mapping.

## 5. Example dataset (used by fixtures and the 200-case demo cohort)

| Case | Name | Product | Profile | Outcome |
|---|---|---|---|---|
| A | Test Person Alpha | Savings | 1990-04-12, 3,000,000, SELF_EMPLOYED, IN | score 16 LOW, AUTO APPROVED |
| B | Test Person One | Savings | as A | screening hit (watchlist `Test Person One`), MANUAL_REVIEW `AML_HIT` |
| C | Test Person Gamma | Current | age 65, 12,000,000, BUSINESS_OWNER, GB | score 45 MEDIUM, MANUAL_REVIEW `RISK_MEDIUM` |
| D | Test Person Delta | NRE | age 65, 12,000,000, CASH_INTENSIVE, KP | score 72 HIGH, MANUAL_REVIEW `RISK_HIGH` |

The seed script `backend/scripts/seed_demo_cohort.py` produces 200 cases with a deterministic random seed, targeting at least 60 percent AUTO approvals (AC-10.6 reports the actual rate).
