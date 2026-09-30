# Account Creation Stub Spec

Stories: E4-S2 (primary), E4-S1, E4-S3. Features: F123-F128.

## Purpose
Stand-in for core banking. Produces a synthetic account number for an APPROVED case. No external call, no real account.

## Behaviour
`create_account(case_id)`: requires state APPROVED; account number is prefix (SAV, CUR, NRE by product) plus 12 digits derived deterministically from the case_id (for example digits of SHA-256). Idempotent: one row per case.

## Account record (append-only)
case_id, product, account_number, created_at (UTC).

## Acceptance Criteria

### AC-07 (account part) Approval triggers stubbed account creation
- AC-07.6 Account numbers match `^(SAV|CUR|NRE)[0-9]{12}$`, prefix matches the product, same case_id yields the same number.
- AC-07.7 Account creation on a non-APPROVED case raises InvalidOnboardingStateException and writes nothing.
- AC-07.8 Calling twice returns the same number and leaves one row.
- AC-07.9 The account table rejects UPDATE and DELETE; the stub performs no network I/O.
- AC-07.10 Creation appends audit ACCOUNT_CREATED with the number masked to its last 4 digits.
- AC-07.11 Auto-approval and APPROVE override both call the stub exactly once per case.

## Non-functional notes
NFR-02, NFR-03 (account number masked in logs and audit).
