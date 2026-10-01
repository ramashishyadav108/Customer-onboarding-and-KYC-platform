# Admin management and analyst queries (spec)

Extends `specs/app_spec.md` section 5 (roles). Source: capstone brief section 6.2 (Admin console: checklists, classification rules, watchlist, users and roles; KYC analyst: manage queries) and NFR-04. All data synthetic. This spec supersedes the v1 note in app_spec section 3 item 6 that excluded checklist editing.

## Roles
| Role | Responsibilities (this spec adds the bold items) |
|---|---|
| prospect | register lead, upload and re-upload documents, track own case, **answer analyst queries on own case** |
| kyc-analyst | review documents, verify or reject, **raise, read and close queries on cases** |
| compliance-officer | manual-review queue, override with reason code |
| admin | **checklists, users, roles**, classification rules, watchlists, reports |

## Authentication and authorization (NFR-04)
- Enforcement stays in the controller layer only (`controllers/dependencies/auth.py`); services and repositories never import it.
- A staff token (kyc-analyst, compliance-officer, admin) is valid only while its user exists and is **active**, and its authority is the user's **current stored role**, not the role claimed in the token. Deactivating a user or changing a role therefore takes effect on the next request.
- Prospect tokens stay case-bound; a prospect can only touch the case in the token.

## Acceptance Criteria

### AC-11 Admin manages users and roles
- AC-11.1 `GET /api/v1/admin/users` (admin) lists users with `user_id`, `username`, `role`, `active`, `created_at`; no password or hash is ever returned.
- AC-11.2 `POST /api/v1/admin/users` (admin) creates a user with `username` (3 to 50 chars of a-z, 0-9, dot, underscore, hyphen), `password` (10 to 128 chars) and `role` in kyc-analyst, compliance-officer, admin. Response 201. The password is stored only as a salted PBKDF2 hash. Invalid input is 422 `VALIDATION_ERROR` with field names; a duplicate username is 409 `USERNAME_TAKEN`.
- AC-11.3 `PUT /api/v1/admin/users/{user_id}/role` changes the role to one of the three staff roles; unknown user is 404; invalid role is 422.
- AC-11.4 `POST /api/v1/admin/users/{user_id}/deactivate` and `/reactivate` toggle `active`. A deactivated user cannot log in (the same generic 401 as a wrong password) and an already issued token stops working immediately (401).
- AC-11.5 After a role change, an already issued token acts with the new role (old admin token of a demoted user gets 403 on admin routes).
- AC-11.6 An admin cannot deactivate or change the role of their own account (409 `SELF_MODIFICATION`), and the last active admin cannot be deactivated or demoted (409 `LAST_ADMIN`).
- AC-11.7 Every create, role change, deactivate and reactivate appends an audit entry (`USER_CREATED`, `USER_ROLE_CHANGED`, `USER_DEACTIVATED`, `USER_REACTIVATED`) holding `user_id` and role values only; never the username-bearing password or any hash.
- AC-11.8 All `/api/v1/admin/users` routes return 401 without a token and 403 for prospect, kyc-analyst and compliance-officer.
- AC-11.9 UI: admin "Users" page lists users, creates a user, changes a role and deactivates or reactivates, with accessible form errors; the admin cannot see action buttons for their own row.

### AC-12 Admin manages product checklists (versioned, append-only)
- AC-12.1 `GET /api/v1/admin/checklists` (admin) returns the latest checklist version per product (Savings, Current, NRE) with items (`item_code`, `mandatory`, `accepted_classes`) and `created_at`.
- AC-12.2 `POST /api/v1/admin/checklists/{product}` (admin) appends a new version `latest + 1` with the supplied items; earlier versions are never modified (append-only, NFR-05 spirit) and existing cases keep the version they were created under (AC-02.3). Response 201 with the new version.
- AC-12.3 Validation (422 `VALIDATION_ERROR`): items non-empty, no duplicate `item_code`, every `item_code` is a known checklist item, `accepted_classes` non-empty and every class a known document class other than UNRECOGNISED, and ID_PROOF, ADDRESS_PROOF and PHOTOGRAPH are present and mandatory. Unknown product is 404.
- AC-12.4 A new case created after publishing gets the new version's checklist (`GET /api/v1/products/{product}/checklist` returns it); a case created earlier still shows its old version.
- AC-12.5 Each new version appends an audit entry `CHECKLIST_VERSION_CREATED` with product and version.
- AC-12.6 All `/api/v1/admin/checklists` routes return 401 without a token and 403 for non-admin roles.
- AC-12.7 UI: admin "Checklists" page shows the latest version per product, lets the admin edit items and publish a new version, with validation messages.

### AC-13 KYC analyst manages queries
- AC-13.1 `POST /api/v1/cases/{case_id}/queries` (kyc-analyst) raises a query with `message` (1 to 500 chars). Response 201 with `query_id`, `status` OPEN. Allowed while the case is INITIATED, DOCS_SUBMITTED, SCREENED, CLASSIFIED or MANUAL_REVIEW; on APPROVED or REJECTED it is 409 `CASE_LOCKED`.
- AC-13.2 `GET /api/v1/cases/{case_id}/queries` (the owning prospect, or any staff role) lists queries oldest first, each with `status` and its responses. A prospect cannot read another case's queries (403).
- AC-13.3 `POST /api/v1/cases/{case_id}/queries/{query_id}/responses` (owning prospect) adds a response (1 to 500 chars) and the query status becomes ANSWERED. A closed query is 409 `QUERY_CLOSED`; a locked case is 409 `CASE_LOCKED`; an unknown query is 404.
- AC-13.4 `POST /api/v1/cases/{case_id}/queries/{query_id}/close` (kyc-analyst) closes the query (status CLOSED); closing twice is 409 `QUERY_CLOSED`.
- AC-13.5 Queries, responses and closures are append-only rows (updates and deletes are rejected); status is derived (OPEN, ANSWERED, CLOSED).
- AC-13.6 Raise, answer and close each append an audit entry (`QUERY_RAISED`, `QUERY_ANSWERED`, `QUERY_CLOSED`) holding `query_id` only. Message text is never written to logs or audit (NFR-03).
- AC-13.7 Role matrix: raise and close are analyst only (401 without token; 403 for prospect, compliance-officer, admin); answering is prospect only.
- AC-13.8 UI: the analyst case page lists queries and lets the analyst raise and close them; the prospect status page shows open queries with a reply form; both with accessible labels and errors.
