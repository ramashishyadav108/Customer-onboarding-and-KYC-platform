# Evaluation: Sprint 2 (sprint-2-documents)

Target: http://127.0.0.1:8010 (fresh throwaway SQLite DB). Date 2026-10-01. Mode: live API via python httpx plus targeted pytest.
IMPORTANT: this contract was authored retrospectively, after the implementation existed (see sprint-contracts/README.md), so it is weaker evidence than a negotiated contract; a pass shows the implementation matches what was observed and cross-checked against the specs.
Verdict: PASS. Contract API checks: 25/25 pass (plus 1 extra evaluator probes, all pass). No failures, so no eval-failures-NNN.json written.

## API checks (every check executed against the live server)
- S2-API-01: PASS. HTTP 201 (expected 201). Assertions: case_id=ok; access_token=ok.  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "INITIATED", "product": "Savings", "access_token":"<redacted>", "token_type": "bearer", "expires_in": 1800}`
- S2-API-02: PASS. HTTP 200 (expected 200).  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "name": "Test Person Alpha", "contact_masked": "********21", "product": "Savings", "state": "INITIATED", "checklist_version": 1, "checklist_items": [{"item_code": "ID_PROOF", "mandatory": true, "accepted_clas`
- S2-API-03: PASS. HTTP 422 (expected 422). Assertions: missing_items=ok; state stays INITIATED=ok.  Body: `{"error": {"code": "MISSING_DOCUMENTS", "message": "Mandatory documents are missing", "details": {"missing_items": ["ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH"]}}}`
- S2-API-04: PASS. HTTP 201 (expected 201). Assertions: document_id=ok; int bp=ok.  Body: `{"document_id": "cada8871-b693-49bf-be56-e4b1d2287623", "checklist_item": "ID_PROOF", "version": 1, "doc_class": "PAN", "status": "VERIFIED", "reason_code": null, "confidence_bp": 9500, "rule_version": 1}`
- S2-API-05: PASS. HTTP 201 (expected 201).  Body: `{"document_id": "a69e0930-4256-4fa7-8a6c-29287bbd2dd7", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "VERIFIED", "reason_code": null, "confidence_bp": 9500, "rule_version": 1}`
- S2-API-06: PASS. HTTP 201 (expected 201).  Body: `{"document_id": "62e74990-eac7-4b68-88a0-f5096f65ef72", "checklist_item": "PHOTOGRAPH", "version": 1, "doc_class": "PHOTOGRAPH", "status": "VERIFIED", "reason_code": null, "confidence_bp": 9500, "rule_version": 1}`
- S2-API-07: PASS. HTTP 200 (expected 200). Assertions: 3 items=ok; sha256, superseded false, no content=ok.  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "documents": [{"document_id": "a69e0930-4256-4fa7-8a6c-29287bbd2dd7", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "VERIFIED", "reason_code": null, "confidence_bp": `
- S2-API-08: PASS. HTTP 200 (expected 200). Assertions: later state than INITIATED=ok. case state now APPROVED  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "DOCS_SUBMITTED", "missing_items": []}`
- S2-API-09: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "INVALID_STATE", "message": "Transition not allowed", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "from_state": "APPROVED", "to_state": "DOCS_SUBMITTED"}}}`
- S2-API-10: PASS. HTTP 422 (expected 422). Assertions: missing_fields=ok.  Body: `{"error": {"code": "MISSING_PROFILE", "message": "Profile is incomplete", "details": {"missing_fields": ["date_of_birth", "annual_income", "occupation_category", "country_code"]}}}`
- S2-API-11: PASS. HTTP 201 (expected 201).  Body: `{"document_id": "a17e3956-5748-4417-abf3-750d25644cd7", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "PAN", "status": "FLAGGED", "reason_code": "DOC_CLASS_MISMATCH", "confidence_bp": 9500, "rule_version": 1}`
- S2-API-12: PASS. HTTP 201 (expected 201).  Body: `{"document_id": "433ea4ef-12eb-4adf-a238-198b0c6c6bc2", "checklist_item": "ADDRESS_PROOF", "version": 2, "doc_class": "UNRECOGNISED", "status": "FLAGGED", "reason_code": "DOC_UNRECOGNISED", "confidence_bp": 0, "rule_version": 1}`
- S2-API-13: PASS. HTTP 415 (expected 415).  Body: `{"error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Unsupported file type", "details": {"allowed": ["pdf", "jpg", "png"]}}}`
- S2-API-14: PASS. HTTP 413 (expected 413). Assertions: max_bytes=ok.  Body: `{"error": {"code": "FILE_TOO_LARGE", "message": "File is too large", "details": {"max_bytes": 5242880}}}`
- S2-API-15: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "UNKNOWN_CHECKLIST_ITEM", "message": "Item is not on the checklist for this product", "details": {"checklist_item": "BOGUS"}}}`
- S2-API-16: PASS. HTTP 201 (expected 201). Assertions: no path echoed=ok.  Body: `{"document_id": "d960f557-adbe-4fce-813d-7ba2423f4a4d", "checklist_item": "ID_PROOF", "version": 1, "doc_class": "PAN", "status": "VERIFIED", "reason_code": null, "confidence_bp": 9500, "rule_version": 1}`
- S2-API-17: PASS. HTTP 403 (expected 403). Assertions: message=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Token is bound to a different case", "details": {}}}`
- S2-API-18: PASS. HTTP 401 (expected 401).  Body: `{"error": {"code": "UNAUTHENTICATED", "message": "Authentication required", "details": {}}}`
- S2-API-20: PASS. HTTP 403 (expected 403). Assertions: required_roles=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["kyc-analyst"]}}}`
- S2-API-21: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "UNKNOWN_REASON_CODE", "message": "Reason code is not allowed for this action", "details": {"allowed": ["DOC_ILLEGIBLE", "DOC_EXPIRED", "DOC_NAME_MISMATCH", "DOC_WRONG_TYPE", "DOC_OTHER"]}}}`
- S2-API-19: PASS. HTTP 200 (expected 200). Assertions: GET case shows REJECTED=ok.  Body: `{"document_id": "ff52eabd-d87b-4884-9a5e-1e715e7235b5", "status": "REJECTED", "reason_code": "DOC_ILLEGIBLE"}`
- S2-API-22: PASS. HTTP 422 (expected 422). Assertions: missing_items==[ADDRESS_PROOF]=ok.  Body: `{"error": {"code": "MISSING_DOCUMENTS", "message": "Mandatory documents are missing", "details": {"missing_items": ["ADDRESS_PROOF"]}}}`
- S2-API-23: PASS. HTTP 201 (expected 201). Assertions: state INITIATED=ok.  Body: `{"document_id": "ecc96ab9-139f-4c03-b9ec-724fabff63fe", "checklist_item": "ADDRESS_PROOF", "version": 2, "doc_class": "UTILITY_BILL", "status": "VERIFIED", "reason_code": null, "confidence_bp": 9500, "rule_version": 1}`
- S2-API-23b(extra: submit unblocked): PASS. HTTP 200 (expected 200).  Body: `{"case_id": "84c88985-e8f0-40cf-a7dc-79ff6361a363", "state": "DOCS_SUBMITTED", "missing_items": []}`
- S2-API-24: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "CASE_LOCKED", "message": "Case is locked", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED"}}}`
- S2-API-25: PASS. HTTP 200 (expected 200). Assertions: 3 mandatory=ok; ID_PROOF classes=FAIL. PASS (re-adjudicated). My script's extra assertion looked up key 'item' but the response key is 'item_code'; status 200, product Savings, 3 items all mandatory, ID_PROOF accepted_classes [PAN, AADHAAR, PASSPORT] are visible in the body below. Evaluator-script bug, not an implementation or contract defect. Body: `{"product": "Savings", "version": 1, "items": [{"item_code": "ID_PROOF", "mandatory": true, "accepted_classes": ["PAN", "AADHAAR", "PASSPORT"]}, {"item_code": "ADDRESS_PROOF", "mandatory": true, "accepted_classes": ["AADHAAR", "PASSPORT", "UTILITY_BILL"]}, {"i`

## Performance (advisory)
- GET /documents 5 calls: 11, 11, 9, 10, 10 ms (limit 1000): PASS

## Pytest / architecture / typing (run from backend/, --no-cov -p no:cacheprovider)
- 518 passed (tests/architecture, test_append_only_triggers, test_classifier, test_upload_signatures, test_documents_domain, test_documents_api, test_submit_reject_api, test_upload_content_validation, test_checklist_api)
- ruff check .: All checks passed. mypy src/: no issues in 106 source files. Full-suite pytest not re-run by me beyond the targeted files above.

## Per-story verdicts
- E2-S1: PASS (API checks and targeted pytest above)
- E2-S2: PASS (API checks and targeted pytest above)
- E2-S3: PASS (API checks and targeted pytest above)
- E2-S4: PASS (API checks and targeted pytest above)

## Not run / limitations
- Playwright/design layers: the contract has none; UI features are covered by the committed Playwright e2e suite (e2e/, 14 mocked tests) and are NOT live-verified by me. No Playwright MCP was used.
- Coverage gate not run (--no-cov).
- Architecture, trigger, append-only and migration-seed checks are proven by pytest only, not live.
- Uploaded content was a few synthetic bytes with real signatures (%PDF-, FFD8FF, 89504E47...) named per the classification stub fixtures.

## Notes
- S2-API-23: the contract says 'version 1 retained, superseded true in the list'. The prospect list returns only the current version per item (superseded false, v2). Version 1 with superseded true is visible only to staff via GET .../documents?include_superseded=true (prospect gets 403 'Only staff may list superseded versions'); I confirmed on a fresh case with analyst1: [(1, superseded True), (2, False)]. Spec AC-09.3b requires only that the earlier version is kept and marked superseded, so the implementation is right and the contract wording is imprecise (should say staff view).
- S2-API-08/24: Case A auto-advanced to APPROVED on submit (state read via GET case), and was then used for the CASE_LOCKED check S2-API-24.
- S2-API-14 used a 6 MiB body starting with %PDF-; S2-API-13 used MZ bytes with application/x-msdownload.
- S2-API-23b is an extra (not in contract): submit after the v2 re-upload returned 200.

## features.json
- All features in this sprint contract's features list set passes=true with last_evaluated set and failure_reason/failure_layer null. UI features outside the contract were left untouched.
