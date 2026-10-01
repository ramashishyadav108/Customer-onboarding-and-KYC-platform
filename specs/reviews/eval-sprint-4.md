# Evaluation: Sprint 4 (sprint-4-review-account)

Target: http://127.0.0.1:8010 (fresh throwaway SQLite DB). Date 2026-10-01. Mode: live API via python httpx plus targeted pytest.
IMPORTANT: this contract was authored retrospectively, after the implementation existed (see sprint-contracts/README.md), so it is weaker evidence than a negotiated contract; a pass shows the implementation matches what was observed and cross-checked against the specs.
Verdict: PASS. Contract API checks: 23/23 pass (plus 0 extra evaluator probes, all pass). No failures, so no eval-failures-NNN.json written.

## API checks (every check executed against the live server)
- S4-API-01: PASS. HTTP 200 (expected 200). Assertions: decision=ok; acct null=ok.  Body: `{"case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "state": "MANUAL_REVIEW", "decision": {"decision_id": "89a4d9bf-72ed-4509-ba09-e6a29297795d", "case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "type": "AUTO", "outcome": "MANUAL_REVIEW", "reason_code": "AML`
- S4-API-02: PASS. HTTP 200 (expected 200). Assertions: steps_run []=ok; AUTO_APPROVED=ok.  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED", "steps_run": [], "decision": {"decision_id": "2083e2ce-c395-4ebb-9235-51dc7d4deafb", "case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "type": "AUTO", "outcome": "APPROVED", "reason_code`
- S4-API-03: PASS. HTTP 200 (expected 200). Assertions: masked=ok; analyst full=ok. analyst: {"case_id":"ef0518f1-980e-40b3-9780-0f44c7cb92c8","product":"Savings","account_number":"SAV817045289620","created_at":"2026-10-01T03:38:51Z"}  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "product": "Savings", "account_number": "SAV********9620", "created_at": "2026-10-01T03:38:51Z"}`
- S4-API-04: PASS. HTTP 404 (expected 404).  Body: `{"error": {"code": "NOT_FOUND", "message": "account not found", "details": {"resource": "account"}}}`
- S4-API-05: PASS. HTTP 200 (expected 200). Assertions: fields=ok; total int=ok; B,C,D present=ok; oldest first=ok. reasons:['AML_HIT', 'RISK_MEDIUM', 'RISK_HIGH', 'AML_HIT', 'PEP_HIT']  Body: `{"items": [{"case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "product": "Savings", "reason_code": "AML_HIT", "age_minutes": 0, "entered_review_at": "2026-10-01T03:38:52Z"}, {"case_id": "cda25ce0-8037-4a24-aa6d-75d1b5567600", "product": "Current", "reason_cod`
- S4-API-06: PASS. HTTP 403 (expected 403). Assertions: roles=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["compliance-officer"]}}}`
- S4-API-07: PASS. HTTP 401 (expected 401).  Body: `{"error": {"code": "UNAUTHENTICATED", "message": "Authentication required", "details": {}}}`
- S4-API-08: PASS. HTTP 200 (expected 200). Assertions: keys=ok; no plaintext contact=ok.  Body: `{"case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "state": "MANUAL_REVIEW", "product": "NRE", "documents": [{"document_id": "cb735c12-d04e-4b83-a074-1217c28a719f", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "AADHAAR", "status": "VERIFIED",`
- S4-API-09: PASS. HTTP 403 (expected 403). Assertions: roles=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["compliance-officer"]}}}`
- S4-API-10: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"fields": [{"field": "reason_code", "message": "Field required"}]}}}`
- S4-API-11: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "UNKNOWN_REASON_CODE", "message": "Reason code is not allowed for this action", "details": {"allowed": ["FALSE_POSITIVE_CLEARED", "RISK_ACCEPTED", "DOCS_CONFIRMED"]}}}`
- S4-API-15: PASS. HTTP 403 (expected 403).  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["compliance-officer"]}}}`
- S4-API-16: PASS. HTTP 422 (expected 422). Assertions: bad band->VALIDATION_ERROR=ok.  Body: `{"error": {"code": "UNKNOWN_REASON_CODE", "message": "Reason code is not allowed for this action", "details": {"allowed": ["NEW_INFORMATION", "SCORING_ERROR", "MANUAL_ASSESSMENT"]}}}`
- S4-API-17: PASS. HTTP 200 (expected 200). Assertions: score int=ok.  Body: `{"assessment_id": "66c74d6c-c911-4ea5-865f-8a50a26ea734", "case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "score": 16, "band": "LOW", "rule_version": 1, "source": "OFFICER_RECLASSIFY", "breakdown": [{"factor": "age", "value_label": "25-60", "points": 0, "we`
- S4-API-12: PASS. HTTP 200 (expected 200). Assertions: override=ok; acct NRE+12=ok.  Body: `{"case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "state": "APPROVED", "override": {"override_id": "c02cc7ea-8fd0-455b-8e51-25b13f5266a8", "case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "actor": "officer1", "previous_state": "MANUAL_REVIEW", "decision": `
- S4-API-13: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "INVALID_STATE", "message": "Transition not allowed", "details": {"case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "from_state": "APPROVED", "to_state": "REJECTED"}}}`
- S4-API-14: PASS. HTTP 200 (expected 200). Assertions: acct null=ok; GET account 404=ok.  Body: `{"case_id": "cda25ce0-8037-4a24-aa6d-75d1b5567600", "state": "REJECTED", "override": {"override_id": "e327b945-9036-4d60-957b-5066a5549519", "case_id": "cda25ce0-8037-4a24-aa6d-75d1b5567600", "actor": "officer1", "previous_state": "MANUAL_REVIEW", "decision": `
- S4-API-18: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "CASE_LOCKED", "message": "Case is locked", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED"}}}`
- S4-API-19: PASS. HTTP 409 (expected 409). Assertions: state APPROVED=ok.  Body: `{"error": {"code": "CASE_LOCKED", "message": "Case is locked", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED"}}}`
- S4-API-20: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "CASE_LOCKED", "message": "Case is locked", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED"}}}`
- S4-API-21: PASS. HTTP 200 (expected 200). Assertions: first APPROVED/notification.approved=ok; then MANUAL_REVIEW, CLASSIFIED=ok; no contact=ok.  Body: `{"case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "notifications": [{"notification_id": "ac85940c-6f5a-4618-8da6-5e00d8dfc347", "case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "event": "APPROVED", "template": "notification.approved", "text": "Your NRE acc`
- S4-API-22: PASS. HTTP 403 (expected 403).  Body: `{"error": {"code": "FORBIDDEN", "message": "Token is bound to a different case", "details": {}}}`
- S4-API-23: PASS. HTTP 200 (expected 200). Assertions: doc rejection notification=ok.  Body: `{"case_id": "84c88985-e8f0-40cf-a7dc-79ff6361a363", "notifications": [{"notification_id": "435e8714-02fe-4230-80a1-a9f89fabd94b", "case_id": "84c88985-e8f0-40cf-a7dc-79ff6361a363", "event": "APPROVED", "template": "notification.approved", "text": "Your Savings`

## Performance (advisory)
- GET /review-queue 5 calls: 7-8 ms (limit 1000): PASS

## Pytest / architecture / typing (run from backend/, --no-cov -p no:cacheprovider)
- 508 passed (test_review_api, test_review_services, test_notifications_api, test_pipeline_e2e, test_pipeline_steps_api, test_masking_accounts_matching, test_append_only_triggers, tests/architecture)
- ruff check .: All checks passed. mypy src/: no issues in 106 source files. Full-suite pytest not re-run by me beyond the targeted files above.

## Per-story verdicts
- E4-S1: PASS (API checks and targeted pytest above)
- E4-S2: PASS (API checks and targeted pytest above)
- E4-S3: PASS (API checks and targeted pytest above)
- E4-S4: PASS (API checks and targeted pytest above)

## Not run / limitations
- Playwright/design layers: the contract has none; UI features are covered by the committed Playwright e2e suite (e2e/, 14 mocked tests) and are NOT live-verified by me. No Playwright MCP was used.
- Coverage gate not run (--no-cov).
- Architecture, trigger, append-only and migration-seed checks are proven by pytest only, not live.
- Uploaded content was a few synthetic bytes with real signatures (%PDF-, FFD8FF, 89504E47...) named per the classification stub fixtures.

## Notes
- S4-API-01 idempotency verified (same decision_id on repeat); S4-API-02 repeat advance returned 200.
- S4-API-17: after reclassify, evidence on case B shows risk_assessment source OFFICER_RECLASSIFY, band LOW, score 16, same breakdown. The 'original RULE_ENGINE row retained' and 'override audit record written' parts are pytest-only (F138); the evidence endpoint shows only the latest assessment, so they are not live-verified.
- S4-API-03: the kyc-analyst token received the full number matching ^SAV\d{12}$.
- Order mattered: review queue (S4-05) was read before any override so B, C and D were all present; then reclassify B, approve D (account NRE + 12 digits), reject C.
- S4-API-23: notifications of the rejected-doc case include DOC_REJECTED / notification.doc_rejected. S4-API-21 order: APPROVED, MANUAL_REVIEW, CLASSIFIED, SCREENED, DOCS_SUBMITTED, INITIATED.
- E4-S5 UI features are excluded from the contract.

## features.json
- All features in this sprint contract's features list set passes=true with last_evaluated set and failure_reason/failure_layer null. UI features outside the contract were left untouched.
