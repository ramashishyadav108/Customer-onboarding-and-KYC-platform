# Accounts, admin management and analyst queries (spec)

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
- AC-11.1 `GET /api/v1/admin/users` (admin) lists users with `user_id`, `username`, `role`, `active`, `created_at` and `status` (ACTIVE, PENDING or DEACTIVATED); no password or hash is ever returned.
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

### AC-14 Prospect sign-up, sign-in and account-linked cases
Staff accounts become usable only through an admin: either the admin creates them (AC-11.2) or a person requests one at sign-up and an admin approves it (AC-14.8, AC-14.9). Self sign-up never grants a staff role by itself.
- AC-14.1 `POST /api/v1/auth/signup` (public) takes `username` (3 to 50 chars of a-z, 0-9, dot, underscore, hyphen) and `password` (10 to 128 chars), creates an active user with role prospect and no case, and returns 201 with `access_token`, `token_type`, `role` prospect, `expires_in` and `case_id` null. Invalid input is 422 `VALIDATION_ERROR` naming the fields; a taken username (including seeded staff names) is 409 `USERNAME_TAKEN`. The password is stored only as a salted PBKDF2 hash.
- AC-14.2 The sign-up body takes an optional `role`: `prospect` (the default) or one of `kyc-analyst`, `compliance-officer`, `admin`. A prospect is active at once. A staff role creates the account **inactive and pending approval**: the response is 201 with `status` PENDING_APPROVAL and **no token**, so the requester has no access of any kind. Any other `role` value is 422 naming `role`.
- AC-14.3 A signed-in prospect account without a case registers a lead with `POST /api/v1/leads` and its bearer token: the case is linked to the account and the response token is bound to that case. A second lead from the same account is 409 `CASE_EXISTS`. Registering with no token still works exactly as before (anonymous lead, case-bound token).
- AC-14.4 `POST /api/v1/auth/login` for a prospect account returns `case_id` (null until a lead exists) and a token bound to that case; it can read and change only that case (403 on any other).
- AC-14.5 Prospect-account tokens stop working when the account is deactivated (401), like staff tokens (AC-11.4); anonymous case tokens (`prospect:<case_id>` subject) are unaffected.
- AC-14.6 Sign-up appends an audit entry `USER_SIGNED_UP` holding `user_id` and role only.
- AC-14.7 UI: a public `/signup` page (account type, username, password, confirm password with inline errors) and a unified `/login` page for prospects and staff with links between them. After sign-in the app redirects by role: prospect without a case to registration, prospect with a case to status, analyst to the workbench, compliance officer to the review queue, admin to the dashboard. Development builds show the synthetic demo staff accounts on the sign-in page; production builds do not.
- AC-14.8 A pending account that signs in with the correct password gets 403 `ACCOUNT_PENDING` ("waiting for administrator approval"); a wrong password is the same generic 401 as always. No token is ever issued to a pending account, and a pending account is never counted as an active admin.
- AC-14.9 Admin approval: `POST /api/v1/admin/users/{user_id}/approve` (optional body `{role}` with a staff role) activates a pending account with the requested or adjusted role and audits `USER_APPROVED`; `POST /api/v1/admin/users/{user_id}/reject` closes the request, leaves the account inactive and audits `USER_REJECTED`. Both are admin only (401 anonymous, 403 other roles); on an account that is not pending they are 409 `NOT_PENDING`; unknown user 404; a non-staff `role` in the approve body is 422.
- AC-14.10 UI: the sign-up page asks "I am a" (Customer, KYC analyst, Compliance officer, Admin) and states that staff accounts need administrator approval; after a staff request it shows a confirmation instead of signing in. The admin Users page shows pending requests with Approve and Reject, and the sign-in page shows the pending message.

### AC-15 Review policy: who approves a case
The brief's AC-07 (auto-approve a clean LOW-risk case) stays the default. A deployment can instead require a compliance officer for every case.
- AC-15.1 Setting `REVIEW_POLICY` is `auto` (default) or `manual`. With `auto` nothing changes: a LOW-risk case with no watchlist hit and every document verified is approved automatically and gets a stubbed account (AC-07).
- AC-15.2 With `manual`, a case that would have been auto-approved goes to MANUAL_REVIEW with decision reason `MANUAL_POLICY`. Every specific reason keeps precedence (AML_HIT, PEP_HIT, DOC_UNRECOGNISED, RISK_MEDIUM, RISK_HIGH).
- AC-15.3 A manual-policy case appears in the compliance officer's review queue with reason MANUAL_POLICY; no account exists until the officer approves (AC-08, which then creates the stubbed account); the officer can also reject. Only the compliance officer can decide it (403 for analyst, admin, prospect). The prospect sees "needs an additional review by our compliance team" until then.
- AC-15.4 An unknown `REVIEW_POLICY` value stops start-up with a configuration error naming `REVIEW_POLICY`.
- AC-15.5 Screening and risk classification still run automatically in both policies (they are rule-based, AC-05 and AC-06); the policy only decides who makes the final approval.
