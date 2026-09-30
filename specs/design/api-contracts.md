# OnboardX API Contracts

Status: DRAFT for `/design` approval. Derived from `specs/app_spec.md`, `specs/*_spec.md`, `specs/stories/`. Machine-readable twin: `api-contracts.schema.json` (OpenAPI 3.0.3). Where this document resolves an open point in the provisional paths of the specs, it is marked **DD-n** (design decision) and listed in `system-design.md` section 9.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1` (except `GET /health`, unversioned) |
| Content type | `application/json` except `POST /cases/{id}/documents` (`multipart/form-data`) |
| Auth | `Authorization: Bearer <access_token>` (HS256 JWT). Roles: `prospect`, `kyc-analyst`, `compliance-officer`, `admin`. Role checks live in controller dependencies only (NFR-04) |
| Correlation | Request header `X-Correlation-ID` optional; always echoed in the response header (NFR-06) |
| Timestamps | UTC ISO-8601 with `Z`, e.g. `2026-10-01T09:30:00Z` |
| Money / ratios / durations | Integers only: INR whole rupees, basis points (`_bp`), seconds (`_seconds`), minutes (`_minutes`). No floats anywhere in any response (NFR-01) |
| IDs | `case_id`, `document_id`, `entry_id` are UUID strings. `version` fields are integers |
| Rate limits | None in v1 (local verification mode, no public exposure). Login is not throttled. Revisit before any non-local deployment |
| Pagination | `GET /cases` only: `page` (default 1), `page_size` (default 25, max 100) |
| PII | `contact` is returned masked (last 2 chars visible, e.g. `********21`). Reports contain aggregates and case_ids only |

### 1.1 Error envelope

Every non-2xx response:

```json
{ "error": { "code": "INVALID_STATE", "message": "Transition not allowed", "details": { } } }
```

| HTTP | code | details shape | Raised when |
|---|---|---|---|
| 401 | `UNAUTHENTICATED` | `{}` | Missing, malformed or expired token; wrong login credentials (login message is generic) |
| 403 | `FORBIDDEN` | `{ "required_roles": [..] }` or `{}` | Role not allowed, or prospect token bound to a different case |
| 404 | `NOT_FOUND` | `{ "resource": "case" }` | Unknown case, document, product, rule-set version, entry |
| 409 | `INVALID_STATE` | `{ "case_id", "from_state", "to_state" }` | `InvalidOnboardingStateException` |
| 409 | `CASE_LOCKED` | `{ "case_id", "state" }` | Write attempted on an APPROVED or REJECTED case (`CaseLockedError`) |
| 409 | `PROFILE_LOCKED` | `{ "case_id", "state" }` | PUT profile after DOCS_SUBMITTED (DD-1: a distinct code, status 409 as specified) |
| 409 | `RULESET_IMMUTABLE` | `{ "version" }` | Edit of a PUBLISHED rule set |
| 413 | `FILE_TOO_LARGE` | `{ "max_bytes": 5242880 }` | Upload over 5 MB |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | `{ "allowed": ["pdf","jpg","png"] }` | Upload type not allowed |
| 422 | `VALIDATION_ERROR` | `{ "fields": [ { "field", "message" } ] }` | Body, query or path validation failure (incl. float in a rule field) |
| 422 | `UNKNOWN_CHECKLIST_ITEM` | `{ "checklist_item" }` | Item not on the case's product checklist |
| 422 | `MISSING_DOCUMENTS` | `{ "missing_items": [ "ADDRESS_PROOF" ] }` | Submit with mandatory items absent |
| 422 | `MISSING_PROFILE` | `{ "missing_fields": [ "country_code" ] }` | Submit with incomplete profile |
| 422 | `MISSING_PROFILE_FIELD` | `{ "field": "annual_income" }` | Classify with a required profile field missing |
| 422 | `RULESET_INVALID` | `{ "reasons": [ "WEIGHTS_SUM", "THRESHOLDS_ORDER" ] }` | Publish of an invalid draft |
| 422 | `UNKNOWN_REASON_CODE` | `{ "allowed": [..] }` | Reason code not in the controlled list for the action |

Machine codes are stable; `message` is human text and never contains PII.

### 1.2 Shared enums

| Enum | Values |
|---|---|
| `Product` | `Savings`, `Current`, `NRE` |
| `CaseState` | `INITIATED`, `DOCS_SUBMITTED`, `SCREENED`, `CLASSIFIED`, `APPROVED`, `REJECTED`, `MANUAL_REVIEW` |
| `Role` | `prospect`, `kyc-analyst`, `compliance-officer`, `admin` |
| `OccupationCategory` | `SALARIED`, `SELF_EMPLOYED`, `BUSINESS_OWNER`, `STUDENT`, `RETIRED`, `CASH_INTENSIVE` |
| `ChecklistItemCode` | `ID_PROOF`, `ADDRESS_PROOF`, `PHOTOGRAPH`, `BUSINESS_PROOF`, `OVERSEAS_ADDRESS_PROOF` |
| `DocClass` | `PAN`, `AADHAAR`, `PASSPORT`, `UTILITY_BILL`, `PHOTOGRAPH`, `GST_CERTIFICATE`, `VISA`, `UNRECOGNISED` |
| `DocStatus` | `VERIFIED`, `FLAGGED`, `REJECTED` |
| `ItemStatus` | `MISSING`, `VERIFIED`, `FLAGGED`, `REJECTED` (the portal chip "Uploaded" is a client-only transient shown between upload request and classification response) |
| `DocReasonCode` (classifier) | `DOC_UNRECOGNISED`, `DOC_CLASS_MISMATCH` |
| `DocRejectReasonCode` (analyst, DD-2 proposed list) | `DOC_ILLEGIBLE`, `DOC_EXPIRED`, `DOC_NAME_MISMATCH`, `DOC_WRONG_TYPE`, `DOC_OTHER` |
| `RiskBand` | `LOW`, `MEDIUM`, `HIGH` |
| `ScreeningReasonCode` | `AML_HIT`, `PEP_HIT` |
| `ReviewReasonCode` (decision routing) | `AML_HIT`, `PEP_HIT`, `DOC_UNRECOGNISED`, `RISK_MEDIUM`, `RISK_HIGH` |
| `OverrideDecision` | `APPROVE`, `REJECT` |
| `OverrideReasonCode` | Approve: `FALSE_POSITIVE_CLEARED`, `RISK_ACCEPTED`, `DOCS_CONFIRMED`. Reject: `CONFIRMED_WATCHLIST_MATCH`, `DOCS_INSUFFICIENT`, `RISK_TOO_HIGH`, `POLICY_OTHER`. A reason code must match the decision direction, else 422 `UNKNOWN_REASON_CODE` (DD-3) |
| `ReclassifyReasonCode` (DD-4 proposed) | `NEW_INFORMATION`, `SCORING_ERROR`, `MANUAL_ASSESSMENT` |
| `NotificationEvent` | `INITIATED`, `DOCS_SUBMITTED`, `SCREENED`, `CLASSIFIED`, `APPROVED`, `REJECTED`, `MANUAL_REVIEW`, `DOC_REJECTED` |

### 1.3 Shared object shapes

**ChecklistItem** `{ item_code, mandatory (bool), accepted_classes: [DocClass] }`

**Checklist** `{ product, version (int), items: [ChecklistItem] }`

**CaseItemView** (checklist item plus current state of that item on a case)
`{ item_code, mandatory, accepted_classes, status: ItemStatus, document_id: uuid|null, doc_version: int|null, doc_class: DocClass|null, reason_code: string|null }`

**ActionRequired** `{ item_code, status: "MISSING"|"FLAGGED"|"REJECTED", reason_code: string|null }` (MISSING carries `null`)

**Profile** `{ date_of_birth: "YYYY-MM-DD", annual_income: int, occupation_category, country_code: "IN", state_code: "PB" }` (`state_code`: two uppercase letters, required when `country_code` is `IN`, omitted otherwise, DD-14)

**CaseDetail**
```json
{
  "case_id": "3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10",
  "name": "Test Person One",
  "contact_masked": "********21",
  "product": "Savings",
  "state": "INITIATED",
  "checklist_version": 1,
  "checklist_items": [ { "item_code": "ID_PROOF", "mandatory": true, "accepted_classes": ["PAN","AADHAAR","PASSPORT"],
                         "status": "VERIFIED", "document_id": "9d1c...", "doc_version": 1, "doc_class": "PAN", "reason_code": null } ],
  "missing_items": ["ADDRESS_PROOF", "PHOTOGRAPH"],
  "action_required": [ { "item_code": "ADDRESS_PROOF", "status": "MISSING", "reason_code": null } ],
  "profile": { "date_of_birth": "1990-04-12", "annual_income": 3000000, "occupation_category": "SELF_EMPLOYED", "country_code": "IN", "state_code": "MH" },
  "profile_complete": true,
  "account_number_masked": null,
  "created_at": "2026-10-01T09:30:00Z",
  "updated_at": "2026-10-01T09:31:12Z"
}
```
`profile` is `null` for staff callers and when not yet supplied (DD-5: staff never need raw income or occupation; the risk breakdown shows bands and points). `account_number_masked` is `"SAV********3456"` only when APPROVED (owner and staff).

**DocumentView** `{ document_id, checklist_item, version, status: DocStatus, doc_class, reason_code|null, confidence_bp: int, rule_version: int, superseded: bool, size_bytes: int, sha256: hex, uploaded_at }`. The stored file name is never returned (NFR-03).

**ScreeningResult** `{ id, case_id, hits: [ { entry_id, list_type: "AML"|"PEP", reason_code: ScreeningReasonCode } ], requires_manual_review: bool, watchlist_version: int, screened_at }`

**RiskAssessment** `{ assessment_id, case_id, score: int 0..100, band, rule_version: int, source: "RULE_ENGINE"|"OFFICER_RECLASSIFY", breakdown: [ { factor: "age"|"income_band"|"occupation_category"|"geography", value_label: string, points: int, weight: int, contribution: int } ], created_at }`. `contribution = points * weight`; `score = sum(contribution) // 100`. `value_label` is a band label such as `"B3"` or `"18-24"`, never raw income or occupation text.

**Decision** `{ decision_id, case_id, type: "AUTO", outcome: "APPROVED"|"MANUAL_REVIEW", reason_code: "AUTO_APPROVED"|ReviewReasonCode, rule_version, actor, created_at }`

**Notification** `{ notification_id, case_id, event: NotificationEvent, template: string, text: string, details: { item_code?, reason_code? }, created_at }`

**RuleSet**
```json
{
  "version": 1, "status": "PUBLISHED",
  "weights": { "age": 20, "income_band": 25, "occupation_category": 30, "geography": 25 },
  "points": {
    "age": [ { "label": "under 18", "min_years": 0, "max_years": 17, "points": 100 },
             { "label": "18-24", "min_years": 18, "max_years": 24, "points": 30 },
             { "label": "25-60", "min_years": 25, "max_years": 60, "points": 0 },
             { "label": "61+", "min_years": 61, "max_years": null, "points": 40 } ],
    "income_band": [ { "code": "B1", "min_inr": 0, "max_inr": 499999, "points": 10 },
                     { "code": "B2", "min_inr": 500000, "max_inr": 2499999, "points": 0 },
                     { "code": "B3", "min_inr": 2500000, "max_inr": 9999999, "points": 30 },
                     { "code": "B4", "min_inr": 10000000, "max_inr": null, "points": 60 } ],
    "occupation_category": { "SALARIED": 0, "RETIRED": 10, "STUDENT": 10, "SELF_EMPLOYED": 30, "BUSINESS_OWNER": 50, "CASH_INTENSIVE": 80 },
    "geography": { "DOMESTIC": 0, "FOREIGN_STANDARD": 30, "DOMESTIC_BORDER": 40, "FOREIGN_HIGH_RISK": 100 }
  },
  "geography_map": { "IN": "DOMESTIC", "GB": "FOREIGN_STANDARD", "US": "FOREIGN_STANDARD", "AE": "FOREIGN_STANDARD", "KP": "FOREIGN_HIGH_RISK", "IR": "FOREIGN_HIGH_RISK" },
  "geography_default": "FOREIGN_STANDARD",
  "border_states": [ "JK", "PB", "AS" ],
  "thresholds": { "low_max": 29, "medium_max": 59 },
  "author": "admin", "created_at": "2026-10-01T00:00:00Z", "published_at": "2026-10-01T00:00:00Z"
}
```
All numbers are integers; a JSON number with a fractional part anywhere in `weights`, `points`, `thresholds` is rejected with 422 `VALIDATION_ERROR`.

**WatchlistEntry** `{ entry_id, name, aliases: [string], list_type: "AML"|"PEP", active: bool, added_at, deactivated_at|null }`

---

## 2. Endpoints

Legend for auth: `public` = no token; otherwise roles allowed. "owner" = prospect token whose `case_id` claim equals the path case; staff = kyc-analyst, compliance-officer, admin unless narrowed.

### 2.1 Platform and auth

#### GET /health
Auth: public. Story E1-S1.
200 `{ "status": "ok" }`. Must answer within 1000 ms of process start.

#### POST /api/v1/auth/login
Auth: public. Story E1-S2.
Request `{ "username": "string", "password": "string" }`.
200 `{ "access_token": "jwt", "token_type": "bearer", "role": Role, "expires_in": 1800, "case_id": uuid|null }`. `case_id` is non-null only for a prospect user bound to a case (DD-6).
401 `UNAUTHENTICATED` with the same body for unknown user and wrong password.
Seeded synthetic users (migration): `prospect1`, `analyst1`, `officer1`, `admin1`; passwords from the seed migration, salted hashes stored.

### 2.2 Leads and cases

#### POST /api/v1/leads
Auth: public (DD-6). Story E1-S3.
Headers: `Idempotency-Key` optional.
Request `{ "name": "1-100 chars", "contact": "10-digit phone or valid email", "product": Product }`.
201 `{ "case_id": uuid, "state": "INITIATED", "product": Product, "access_token": "jwt", "token_type": "bearer", "expires_in": 1800 }`. The token has role `prospect` and is bound to the new `case_id` (DD-6).
200 same body when the same `Idempotency-Key` with an identical payload is replayed; a replay with a different payload returns 422 `VALIDATION_ERROR` with field `Idempotency-Key`.
422 `VALIDATION_ERROR` with the full field list; no case row is created.
Side effects in one transaction: case row, state-history INITIATED, audit `LEAD_CREATED`, notification `INITIATED`.

#### GET /api/v1/cases
Auth: kyc-analyst, compliance-officer, admin. Story E3-S5 (workbench). DD-7 (endpoint added).
Query: `state` (CaseState), `product` (Product), `sort` (`age_desc` default = oldest first, `age_asc`), `page`, `page_size`.
200 `{ "items": [ { "case_id", "product", "state", "age_minutes": int, "created_at" } ], "page": 1, "page_size": 25, "total": 130 }`. No name or contact in the list.
422 invalid filter.

#### GET /api/v1/cases/{case_id}
Auth: owner, kyc-analyst, compliance-officer, admin. Stories E1-S3, E2-S4.
200 `CaseDetail`. 403 for a prospect token bound to another case. 404 unknown case.

#### PUT /api/v1/cases/{case_id}/profile
Auth: owner. Story E1-S3.
Request `Profile`. `annual_income` must be a JSON integer.
200 `CaseDetail`. 409 `PROFILE_LOCKED` once DOCS_SUBMITTED or later. 422 `VALIDATION_ERROR` (non-integer income, bad date, unknown occupation, country not two uppercase letters, date of birth in future).
Audit `PROFILE_UPDATED` (field names only).

### 2.3 Checklist and documents

#### GET /api/v1/products/{product}/checklist
Auth: any authenticated user. Story E1-S5.
200 `Checklist` (latest version). 404 `NOT_FOUND` for unknown product. 422 not applicable (unknown product is 404).

#### POST /api/v1/cases/{case_id}/documents
Auth: owner only (analyst cannot upload). Stories E2-S1, E2-S4.
Content type `multipart/form-data`: `checklist_item` (ChecklistItemCode), `file` (pdf, jpg, png, max 5 MB).
201 `{ "document_id", "checklist_item", "version": 1, "doc_class", "status": "VERIFIED"|"FLAGGED", "reason_code": null|"DOC_UNRECOGNISED"|"DOC_CLASS_MISMATCH", "confidence_bp": 9500, "rule_version": 1 }`.
Re-upload for a filled item creates `version` n+1 and marks the previous `superseded` (allowed in INITIATED, DOCS_SUBMITTED, MANUAL_REVIEW). No state change, no state-history row.
403 not owner. 409 `CASE_LOCKED` on APPROVED or REJECTED. 409 `INVALID_STATE` in SCREENED and CLASSIFIED (DD-8: the specs allow uploads only in INITIATED, DOCS_SUBMITTED and MANUAL_REVIEW; the two mid-pipeline states are transient and frozen). 413, 415, 422 `UNKNOWN_CHECKLIST_ITEM`.

#### GET /api/v1/cases/{case_id}/documents
Auth: owner, kyc-analyst, compliance-officer, admin. Story E2-S1.
200 `{ "case_id", "documents": [ DocumentView ] }` current version per item; `?include_superseded=true` adds history (staff only).

#### POST /api/v1/cases/{case_id}/documents/{document_id}/reject
Auth: kyc-analyst. Story E2-S4.
Request `{ "reason_code": DocRejectReasonCode, "comment": "optional, max 500" }`.
200 `{ "document_id", "status": "REJECTED", "reason_code" }`. Appends a rejection row, audit `DOCUMENT_REJECTED`, notification `DOC_REJECTED` with `item_code` and `reason_code`.
403 other roles. 404 unknown document. 409 `CASE_LOCKED`. 422 `UNKNOWN_REASON_CODE` or missing reason.

#### POST /api/v1/cases/{case_id}/submit
Auth: owner. Story E2-S2.
No body.
200 `{ "case_id", "state": "DOCS_SUBMITTED", "missing_items": [] }`. Repeat while DOCS_SUBMITTED returns 200 idempotently without a second history row.
422 `MISSING_DOCUMENTS` (state stays INITIATED), 422 `MISSING_PROFILE`. 409 `INVALID_STATE` in any later state.
A mandatory item counts as present when its current document is VERIFIED or FLAGGED; REJECTED or absent blocks submit (DD-9: a flagged document is allowed through because the decision step routes it to MANUAL_REVIEW with `DOC_UNRECOGNISED`).
Audit `DOCUMENTS_SUBMITTED` with document ids.

### 2.4 Pipeline steps

#### POST /api/v1/cases/{case_id}/screen
Auth: kyc-analyst, admin. Story E3-S1.
200 `{ "state": "SCREENED", "result": ScreeningResult }`. Repeat on SCREENED with unchanged watchlist version returns the existing result, no new transition. 409 `INVALID_STATE` from any other state. Logs carry case_id and hit count only.

#### POST /api/v1/cases/{case_id}/classify
Auth: kyc-analyst, admin. Story E3-S3.
200 `{ "case_id", "state": "CLASSIFIED", "assessment": RiskAssessment }`.
409 `INVALID_STATE` unless SCREENED. 422 `MISSING_PROFILE_FIELD`, state unchanged.

#### POST /api/v1/cases/{case_id}/decide
Auth: kyc-analyst, admin (the in-process system actor calls the service directly). Story E4-S1.
200 `{ "case_id", "state": "APPROVED"|"MANUAL_REVIEW", "decision": Decision, "account_number": string|null }`. Repeat returns the original decision, no second row. `account_number` is returned only when this call or the original created it (full number; callers are staff; logs mask).
409 `INVALID_STATE` unless CLASSIFIED (or already decided: returns original). 409 `CASE_LOCKED` never for repeat decide on APPROVED (returns original), only for a mutation attempt.

#### POST /api/v1/cases/{case_id}/advance
Auth: kyc-analyst, admin. Story E4-S1.
Runs pending steps in order on a DOCS_SUBMITTED case.
200 `{ "case_id", "state": CaseState, "steps_run": ["screen","classify","decide"], "decision": Decision|null }`. Repeat returns the same state, `steps_run: []`, no new history rows.
409 `INVALID_STATE` when the case is INITIATED.
Failure mid-way: steps already committed stay committed; the response is the error for the failing step and the case sits at the last good state, so a retry resumes.

#### GET /api/v1/cases/{case_id}/evidence
Auth: kyc-analyst, compliance-officer, admin. Stories E3-S5, E4-S5. DD-7 (endpoint added).
200 `{ "case_id", "state", "product", "documents": [DocumentView], "screening": ScreeningResult|null, "risk_assessment": RiskAssessment|null, "decision": Decision|null, "override": OverrideView|null, "review_reason_code": ReviewReasonCode|null, "account_number_masked": string|null }`. `risk_assessment` is the latest (including officer reclassification).

### 2.5 Review

#### GET /api/v1/review-queue
Auth: compliance-officer only. Story E4-S3.
200 `{ "items": [ { "case_id", "product", "reason_code": ReviewReasonCode, "age_minutes": int, "entered_review_at" } ], "total": int }` oldest first. 403 every other role.

#### POST /api/v1/cases/{case_id}/override
Auth: compliance-officer only. Story E4-S3.
Request `{ "decision": "APPROVE"|"REJECT", "reason_code": OverrideReasonCode, "comment": "optional, max 500" }`.
200 `{ "case_id", "state": "APPROVED"|"REJECTED", "override": OverrideView, "account_number": "SAV123456789012"|null }`. `OverrideView = { override_id, case_id, actor, previous_state: "MANUAL_REVIEW", decision, reason_code, comment, rule_version, created_at }`. Account number present only for APPROVE.
403 every other role. 409 `INVALID_STATE` when not MANUAL_REVIEW. 422 missing or unknown reason (state unchanged).

#### POST /api/v1/cases/{case_id}/reclassify
Auth: compliance-officer only. Story E4-S3.
Request `{ "band": RiskBand, "reason_code": ReclassifyReasonCode, "comment": "optional" }`.
200 `RiskAssessment` with `source: "OFFICER_RECLASSIFY"` (score copied from the previous assessment, band as requested, `rule_version` unchanged) plus audit `RISK_RECLASSIFIED` (actor, previous band, new band, reason). Allowed only in MANUAL_REVIEW (DD-10); reclassification never changes the state and never auto-approves.
409 `INVALID_STATE` or `CASE_LOCKED`. 422 missing reason (original band stays in force).

#### GET /api/v1/cases/{case_id}/notifications
Auth: owner only (others 403, including staff: the spec restricts the read to the owning prospect). Story E4-S4.
200 `{ "case_id", "notifications": [ Notification ] }` newest first. Text never contains contact data.

### 2.6 Admin: rule sets

All 403 for non-admin. Story E3-S4.

| Method and path | Request | Success | Errors |
|---|---|---|---|
| `GET /api/v1/admin/rule-sets` | none | 200 `{ "items": [ { version, status, author, created_at, published_at } ] }` | |
| `GET /api/v1/admin/rule-sets/{version}` | none | 200 `RuleSet` | 404 |
| `POST /api/v1/admin/rule-sets` | none | 201 `RuleSet` (DRAFT copy of the latest version, version = max + 1) | 409 if a DRAFT already exists (`DRAFT_EXISTS`, DD-11) |
| `PUT /api/v1/admin/rule-sets/{version}` | `RuleSet` fields: `weights`, `points`, `geography_map`, `geography_default`, `thresholds` | 200 `RuleSet` | 404, 409 `RULESET_IMMUTABLE`, 422 (floats, bad types) |
| `POST /api/v1/admin/rule-sets/{version}/publish` | none | 200 `RuleSet` status PUBLISHED with `published_at` | 409 `RULESET_IMMUTABLE` if already published, 422 `RULESET_INVALID` (weights not summing to 100, thresholds not strictly ascending with `low_max < medium_max < 100`) |

Audit events: `RULESET_DRAFT_CREATED`, `RULESET_DRAFT_UPDATED`, `RULESET_PUBLISHED` with actor and version.

### 2.7 Admin: watchlist

All 403 for non-admin. Story E3-S4.

| Method and path | Request | Success | Errors |
|---|---|---|---|
| `GET /api/v1/admin/watchlist` | `?active=true\|false` optional | 200 `{ "watchlist_version": int, "items": [ WatchlistEntry ] }` | |
| `POST /api/v1/admin/watchlist` | `{ "name": string 1-100, "aliases": [string] (max 10), "list_type": "AML"\|"PEP" }` | 201 `WatchlistEntry` | 422 |
| `POST /api/v1/admin/watchlist/{entry_id}/deactivate` | none | 200 `WatchlistEntry` (active false) | 404, 409 `ALREADY_DEACTIVATED` (DD-11) |

There is no delete and no edit. Audit events `WATCHLIST_ENTRY_ADDED`, `WATCHLIST_ENTRY_DEACTIVATED`. Audit and logs do not combine a name with list details (NFR-03 spirit, AC-05.10); audit payload holds `entry_id` and `list_type` only.

### 2.8 Admin: reports

Auth: admin only (401 without token, 403 otherwise). Story E5-S3. Common query parameters: `product` (Product), `from`, `to` (ISO dates `YYYY-MM-DD`, inclusive; `from` <= `to`). Invalid value: 422 `VALIDATION_ERROR` with `fields[0].field` naming the parameter. Empty data returns zeros and empty arrays, never an error. Bodies contain aggregates and case_ids only.

| Path | 200 body |
|---|---|
| `GET /api/v1/admin/reports/tat` | `{ "filters": {..}, "items": [ { "product", "count", "avg_seconds", "min_seconds", "max_seconds" } ] }` (one row per product present; closed cases only; filter by INITIATED date) |
| `GET /api/v1/admin/reports/funnel` | `{ "filters", "stages": [ { "stage": "INITIATED"\|"DOCS_SUBMITTED"\|"SCREENED"\|"CLASSIFIED"\|"APPROVED"\|"REJECTED", "count", "conversion_bp" } ] }` (conversion from the previous stage; APPROVED and REJECTED convert from CLASSIFIED; INITIATED is 10000 when count > 0; MANUAL_REVIEW is reported as a stage `MANUAL_REVIEW` between CLASSIFIED and the outcomes for cases that ever entered it, DD-12) |
| `GET /api/v1/admin/reports/backlog` | `{ "filters", "count", "oldest_age_minutes", "buckets": [ { "label": "under_60", "min_minutes": 0, "max_minutes": 59, "count" }, { "label": "60_to_1440", ... }, { "label": "over_1440", ... } ] }` (current snapshot; `from`/`to` filter on time entered MANUAL_REVIEW) |
| `GET /api/v1/admin/reports/time-per-stage` | `{ "filters", "stages": [ { "from_state", "to_state", "count", "avg_seconds" } ] }` |
| `GET /api/v1/admin/reports/rejection-reasons` | `{ "filters", "items": [ { "reason_code", "count" } ] }` (max 5, count desc then code asc, REJECTED cases via override rows) |
| `GET /api/v1/admin/reports/auto-approval` | `{ "filters", "auto_approved": int, "decided": int, "rate_bp": int, "target_bp": 6000, "met": bool }` |

---

## 3. Endpoint summary (role matrix)

| Endpoint | public | prospect (owner) | kyc-analyst | compliance-officer | admin |
|---|---|---|---|---|---|
| GET /health | x | x | x | x | x |
| POST /auth/login | x | x | x | x | x |
| POST /leads | x | x | | | |
| GET /cases | | | x | x | x |
| GET /cases/{id} | | x | x | x | x |
| PUT /cases/{id}/profile | | x | | | |
| GET /products/{p}/checklist | | x | x | x | x |
| POST /cases/{id}/documents | | x | | | |
| GET /cases/{id}/documents | | x | x | x | x |
| POST /cases/{id}/documents/{d}/reject | | | x | | |
| POST /cases/{id}/submit | | x | | | |
| POST /cases/{id}/screen, /classify, /decide, /advance | | | x | | x |
| GET /cases/{id}/evidence | | | x | x | x |
| GET /review-queue | | | | x | |
| POST /cases/{id}/override, /reclassify | | | | x | |
| GET /cases/{id}/notifications | | x | | | |
| /admin/rule-sets, /admin/watchlist, /admin/reports/* | | | | | x |

## 4. Audit event catalogue

`LEAD_CREATED`, `PROFILE_UPDATED`, `DOCUMENT_UPLOADED`, `DOCUMENT_REJECTED`, `DOCUMENTS_SUBMITTED`, `STATE_TRANSITION`, `CASE_SCREENED`, `CASE_CLASSIFIED`, `DECISION_RECORDED`, `ACCOUNT_CREATED` (number masked to last 4), `OVERRIDE_APPLIED`, `RISK_RECLASSIFIED`, `RULESET_DRAFT_CREATED`, `RULESET_DRAFT_UPDATED`, `RULESET_PUBLISHED`, `WATCHLIST_ENTRY_ADDED`, `WATCHLIST_ENTRY_DEACTIVATED`. Every row: `actor`, `role`, `case_id|null`, `event`, `payload` (PII-free JSON), `correlation_id`, UTC timestamp.
