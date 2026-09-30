# Lead Capture Spec

Stories: E1-S3 (primary), E1-S2, E1-S4, E2-S5 (UI). Features: F019-F027, F069-F070.

## Purpose
A prospect registers interest and receives a `case_id`. A profile step then supplies the inputs the risk rules need.

## Data
- Lead: name (1-100 chars), contact (10-digit phone or valid email), product (Savings | Current | NRE).
- Profile: date_of_birth, annual_income (integer INR), occupation_category (SALARIED, SELF_EMPLOYED, BUSINESS_OWNER, STUDENT, RETIRED, CASH_INTENSIVE), country_code (ISO 3166-1 alpha-2), state_code (ISO 3166-2 subdivision suffix, e.g. PB; required when country_code is IN, otherwise omitted).
- PII: contact, income and occupation are never logged; contact is masked on read (last 2 characters).

## Endpoints (provisional)
| Method and path | Role | Result |
|---|---|---|
| POST /api/v1/leads | public or prospect | 201 `{case_id, state: INITIATED}` |
| GET /api/v1/cases/{case_id} | owner, staff | state, product, checklist, action_required, missing_items, masked contact |
| PUT /api/v1/cases/{case_id}/profile | owner | 200, or 409 once DOCS_SUBMITTED |

## Acceptance Criteria

### AC-01 Register lead with name, contact, product and get INITIATED plus case_id
- AC-01.1 A valid POST returns 201, a UUID `case_id`, state INITIATED, for each of Savings, Current, NRE.
- AC-01.2 A missing name, missing contact, malformed contact or product outside the enum returns 422 with a field-level error list; no case row is created.
- AC-01.3 Creation appends audit LEAD_CREATED and an INITIATED state-history row in one transaction.
- AC-01.4 GET case returns state, product, checklist version and items, with contact masked.
- AC-01.5 PUT profile stores the four profile fields while INITIATED; non-integer income returns 422; after DOCS_SUBMITTED it returns 409.
- AC-01.6 The same Idempotency-Key returns the same `case_id` and leaves one case row.
- AC-01.7 UI: the lead form shows accessible inline errors and the `case_id` on success, and works at 360 px and 1280 px.

## Non-functional notes
NFR-03 (no PII in logs), NFR-04 (prospect bound to own case), NFR-06 (correlation ID and case_id in logs).

## Out of scope
Email or phone verification, duplicate-person detection.
