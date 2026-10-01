# Evaluation: Sprint 3 (sprint-3-screening-risk)

Target: http://127.0.0.1:8010 (fresh throwaway SQLite DB). Date 2026-10-01. Mode: live API via python httpx plus targeted pytest.
IMPORTANT: this contract was authored retrospectively, after the implementation existed (see sprint-contracts/README.md), so it is weaker evidence than a negotiated contract; a pass shows the implementation matches what was observed and cross-checked against the specs.
Verdict: PASS. Contract API checks: 22/22 pass (plus 2 extra evaluator probes, all pass). No failures, so no eval-failures-NNN.json written.

## API checks (every check executed against the live server)
- S3-API-01: PASS. HTTP 200 (expected 200). Assertions: later state MANUAL_REVIEW=ok. state MANUAL_REVIEW  Body: `{"case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "state": "DOCS_SUBMITTED", "missing_items": []}`
- S3-API-02: PASS. HTTP 200 (expected 200). Assertions: hit0=ok; requires_manual_review=ok; decision=ok; history ends=ok.  Body: `{"case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "state": "MANUAL_REVIEW", "product": "Savings", "documents": [{"document_id": "4c32de7e-c457-43ae-aa39-7cd3f68e15a9", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "V`
- S3-API-03: PASS. HTTP 200 (expected 200). Assertions: hits []=ok; rmr false=ok.  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED", "product": "Savings", "documents": [{"document_id": "a69e0930-4256-4fa7-8a6c-29287bbd2dd7", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "VERIFI`
- S3-API-04: PASS. HTTP 200 (expected 200). Assertions: score16 LOW RULE_ENGINE=ok.  Body: `{"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "state": "APPROVED", "product": "Savings", "documents": [{"document_id": "a69e0930-4256-4fa7-8a6c-29287bbd2dd7", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "VERIFI`
- S3-API-05: PASS. HTTP 200 (expected 200). Assertions: 45 MEDIUM=ok.  Body: `{"case_id": "cda25ce0-8037-4a24-aa6d-75d1b5567600", "state": "MANUAL_REVIEW", "product": "Current", "documents": [{"document_id": "1e83eba1-1d10-4a58-98fc-bb3195a4d9ef", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "UTILITY_BILL", "status": "V`
- S3-API-06: PASS. HTTP 200 (expected 200). Assertions: 72 HIGH=ok.  Body: `{"case_id": "e2e95e15-15a1-44a8-800c-94982b941699", "state": "MANUAL_REVIEW", "product": "NRE", "documents": [{"document_id": "cb735c12-d04e-4b83-a074-1217c28a719f", "checklist_item": "ADDRESS_PROOF", "version": 1, "doc_class": "AADHAAR", "status": "VERIFIED",`
- S3-API-07: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "INVALID_STATE", "message": "Transition not allowed", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "from_state": "APPROVED", "to_state": "SCREENED"}}}`
- S3-API-07b(extra MANUAL_REVIEW case): PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "INVALID_STATE", "message": "Transition not allowed", "details": {"case_id": "99b34d46-24c3-4290-b39b-91547a7a845d", "from_state": "MANUAL_REVIEW", "to_state": "SCREENED"}}}`
- S3-API-08: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "INVALID_STATE", "message": "Transition not allowed", "details": {"case_id": "ef0518f1-980e-40b3-9780-0f44c7cb92c8", "from_state": "APPROVED", "to_state": "CLASSIFIED"}}}`
- S3-API-09: PASS. HTTP 403 (expected 403). Assertions: roles=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin", "kyc-analyst"]}}}`
- S3-API-10: PASS. HTTP 200 (expected 200). Assertions: v1 PUBLISHED=ok; fields=ok.  Body: `{"items": [{"version": 1, "status": "PUBLISHED", "author": "system", "created_at": "2026-10-01T00:00:00Z", "published_at": "2026-10-01T00:00:00Z"}]}`
- S3-API-11: PASS. HTTP 409 (expected 409). Assertions: version 1=ok.  Body: `{"error": {"code": "RULESET_IMMUTABLE", "message": "Published rule set is immutable", "details": {"version": 1}}}`
- S3-API-12: PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "RULESET_IMMUTABLE", "message": "Published rule set is immutable", "details": {"version": 1}}}`
- S3-API-13: PASS. HTTP 201 (expected 201). Assertions: weights=ok.  Body: `{"version": 2, "status": "DRAFT", "weights": {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25}, "points": {"age": [{"label": "under 18", "min_years": 0, "max_years": 17, "points": 100}, {"label": "18-24", "min_years": 18, "max_years": `
- S3-API-14: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"fields": [{"field": "weights.age", "message": "Input should be a valid integer"}]}}}`
- S3-API-15: PASS. HTTP 200 (expected 200).  Body: `{"version": 2, "status": "DRAFT", "weights": {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25}, "points": {"age": [{"label": "under 18", "min_years": 0, "max_years": 17, "points": 100}, {"label": "18-24", "min_years": 18, "max_years": `
- S3-API-16: PASS. HTTP 200 (expected 200).  Body: `{"version": 2, "status": "PUBLISHED", "weights": {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25}, "points": {"age": [{"label": "under 18", "min_years": 0, "max_years": 17, "points": 100}, {"label": "18-24", "min_years": 18, "max_year`
- S3-API-16b(extra PUT after publish): PASS. HTTP 409 (expected 409).  Body: `{"error": {"code": "RULESET_IMMUTABLE", "message": "Published rule set is immutable", "details": {"version": 2}}}`
- S3-API-17: PASS. HTTP 403 (expected 403). Assertions: roles=ok.  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S3-API-18: PASS. HTTP 200 (expected 200). Assertions: 5 AML 5 PEP=ok; Test Person One entry=ok; int watchlist_version=ok. total entries 10  Body: `{"watchlist_version": 10, "items": [{"entry_id": "10000000-0000-4000-8000-000000000001", "name": "Test Person One", "aliases": ["T P One"], "list_type": "AML", "active": true, "added_at": "2026-10-01T00:00:00Z", "deactivated_at": null}, {"entry_id": "10000000-`
- S3-API-19: PASS. HTTP 201 (expected 201). Assertions: entry_id,deactivated_at null=ok.  Body: `{"entry_id": "3ec6b8ff-87a8-4528-8e75-c4a5220d6868", "name": "Test Person Zeta", "aliases": [], "list_type": "AML", "active": true, "added_at": "2026-10-01T03:38:53Z", "deactivated_at": null}`
- S3-API-20: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "details": {"fields": [{"field": "list_type", "message": "must be AML or PEP"}]}}}`
- S3-API-21: PASS. HTTP 200 (expected 200). Assertions: deactivated_at set=ok; still listed=ok.  Body: `{"entry_id": "a73ed308-a0f0-4603-a6e1-af476b965af7", "name": "Test Person Eta", "aliases": [], "list_type": "PEP", "active": false, "added_at": "2026-10-01T03:38:54Z", "deactivated_at": "2026-10-01T03:38:54Z"}`
- S3-API-22: PASS. HTTP 403 (expected 403).  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`

## Performance (advisory)
- GET /admin/rule-sets 5 calls: 8, 7, 9, 7, 9 ms (limit 1000): PASS

## Pytest / architecture / typing (run from backend/, --no-cov -p no:cacheprovider)
- 515 passed (test_risk_ruleset, test_risk_scoring, test_screening_decision_domain, test_admin_rule_sets_api, test_admin_watchlist_api, test_rule_set_service, test_seed_migrations, test_append_only_triggers, tests/architecture)
- ruff check .: All checks passed. mypy src/: no issues in 106 source files. Full-suite pytest not re-run by me beyond the targeted files above.

## Per-story verdicts
- E3-S1: PASS (API checks and targeted pytest above)
- E3-S3: PASS (API checks and targeted pytest above)
- E3-S4: PASS (API checks and targeted pytest above)

## Not run / limitations
- Playwright/design layers: the contract has none; UI features are covered by the committed Playwright e2e suite (e2e/, 14 mocked tests) and are NOT live-verified by me. No Playwright MCP was used.
- Coverage gate not run (--no-cov).
- Architecture, trigger, append-only and migration-seed checks are proven by pytest only, not live.
- Uploaded content was a few synthetic bytes with real signatures (%PDF-, FFD8FF, 89504E47...) named per the classification stub fixtures.

## Notes
- S3-API-13 created rule set v2 (DRAFT); S3-API-15/16 set integer weights equal to v1 and published it, so scores are unchanged. Cases C and D were scored (45 MEDIUM, 72 HIGH) before publishing in any case.
- S3-API-19: after adding Test Person Zeta (AML) a new case for that name went to MANUAL_REVIEW / AML_HIT (verified). S3-API-21: Test Person Eta was added as PEP; a case created before deactivation went to MANUAL_REVIEW; after deactivation a new Eta case reached APPROVED, and the entry stayed in the listing with deactivated_at set.
- S3-API-07b and 16b are extra probes beyond the contract.
- Layering/trigger/append-only claims are proven by pytest only, not live.

## features.json
- All features in this sprint contract's features list set passes=true with last_evaluated set and failure_reason/failure_layer null. UI features outside the contract were left untouched.
