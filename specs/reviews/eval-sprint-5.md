# Evaluation: Sprint 5 (sprint-5-reports-admin)

Target: http://127.0.0.1:8010 (fresh throwaway SQLite DB). Date 2026-10-01. Mode: live API via python httpx plus targeted pytest.
IMPORTANT: this contract was authored retrospectively, after the implementation existed (see sprint-contracts/README.md), so it is weaker evidence than a negotiated contract; a pass shows the implementation matches what was observed and cross-checked against the specs.
Verdict: PASS. Contract API checks: 20/20 pass (plus 0 extra evaluator probes, all pass). No failures, so no eval-failures-NNN.json written.

## API checks (every check executed against the live server)
- S5-API-01: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; items per product ints=ok.  Body: `{"filters": {"product": null, "from": null, "to": null}, "items": [{"product": "Current", "count": 1, "avg_seconds": 3, "min_seconds": 3, "max_seconds": 3}, {"product": "NRE", "count": 1, "avg_seconds": 2, "min_seconds": 2, "max_seconds": 2}, {"product": "Savi`
- S5-API-02: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; stages order=ok; ints=ok.  Body: `{"filters": {"product": null, "from": null, "to": null}, "stages": [{"stage": "INITIATED", "count": 11, "conversion_bp": 10000}, {"stage": "DOCS_SUBMITTED", "count": 8, "conversion_bp": 7272}, {"stage": "SCREENED", "count": 8, "conversion_bp": 10000}, {"stage"`
- S5-API-03: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; fields=FAIL. PASS (re-adjudicated). My script's extra assertion treated buckets as a dict; the response has buckets as a list of {label, min_minutes, max_minutes, count} with labels under_60, 60_to_1440, over_1440 (re-confirmed in a second call). count and oldest_age_minutes present. Evaluator-script bug, not an implementation defect. Body: `{"filters": {"product": null, "from": null, "to": null}, "count": 3, "oldest_age_minutes": 0, "buckets": [{"label": "under_60", "min_minutes": 0, "max_minutes": 59, "count": 3}, {"label": "60_to_1440", "min_minutes": 60, "max_minutes": 1440, "count": 0}, {"lab`
- S5-API-04: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; stages list=ok.  Body: `{"filters": {"product": null, "from": null, "to": null}, "stages": [{"from_state": "CLASSIFIED", "to_state": "APPROVED", "count": 3, "avg_seconds": 0}, {"from_state": "CLASSIFIED", "to_state": "MANUAL_REVIEW", "count": 5, "avg_seconds": 0}, {"from_state": "DOC`
- S5-API-05: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; items ranked desc=ok.  Body: `{"filters": {"product": null, "from": null, "to": null}, "items": [{"reason_code": "RISK_TOO_HIGH", "count": 1}]}`
- S5-API-06: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; fields=ok.  Body: `{"filters": {"product": null, "from": null, "to": null}, "auto_approved": 3, "decided": 8, "rate_bp": 3750, "target_bp": 6000, "met": false}`
- S5-API-07: PASS. HTTP 200 (expected 200). Assertions: no PII=ok; fields=ok.  Body: `{"older_than_days": 7, "total": 0, "stages": [{"stage": "INITIATED", "count": 0}, {"stage": "DOCS_SUBMITTED", "count": 0}]}`
- S5-API-08: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. tat (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-09: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. funnel (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-10: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. backlog (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-11: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. time-per-stage (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-12: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. rejection-reasons (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-13: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. auto-approval (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-14: PASS. HTTP 403 (expected 403). Assertions: required_roles [admin]=ok. dropped-leads (officer)  Body: `{"error": {"code": "FORBIDDEN", "message": "Role not permitted", "details": {"required_roles": ["admin"]}}}`
- S5-API-15: PASS. HTTP 401 (expected 401).  Body: `{"error": {"code": "UNAUTHENTICATED", "message": "Authentication required", "details": {}}}`
- S5-API-16: PASS. HTTP 422 (expected 422). Assertions: field product=ok.  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"fields": [{"field": "product", "message": "Input should be 'Savings', 'Current' or 'NRE'"}]}}}`
- S5-API-17: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "details": {"fields": [{"field": "from", "message": "from must not be after to"}]}}}`
- S5-API-18: PASS. HTTP 422 (expected 422).  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "details": {"fields": [{"field": "from", "message": "must be an ISO date YYYY-MM-DD"}]}}}`
- S5-API-19: PASS. HTTP 422 (expected 422). Assertions: field=ok.  Body: `{"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"fields": [{"field": "older_than_days", "message": "Input should be greater than or equal to 1"}]}}}`
- S5-API-20: PASS. HTTP 200 (expected 200). Assertions: NRE-only: INITIATED count == 1 (only Delta)=ok. body:{"filters":{"product":"NRE","from":"2026-01-01","to":"2026-12-31"},"stages":[{"stage":"INITIATED","count":1,"conversion_bp":10000},{"stage":"DOCS_SUBMITTED","count":1,"conversion_bp":10000},{"sta  Body: `{"filters": {"product": "NRE", "from": "2026-01-01", "to": "2026-12-31"}, "stages": [{"stage": "INITIATED", "count": 1, "conversion_bp": 10000}, {"stage": "DOCS_SUBMITTED", "count": 1, "conversion_bp": 10000}, {"stage": "SCREENED", "count": 1, "conversion_bp":`

## Performance (advisory)
- 6 report endpoints, 5 calls each, 6-10 ms (limit 500): PASS

## Pytest / architecture / typing (run from backend/, --no-cov -p no:cacheprovider)
- 485 passed (test_reports_api, test_reports_performance, test_reports_domain, test_role_matrix, test_append_only_triggers, test_review_logging, test_pipeline_logging_concurrency, test_redaction, tests/architecture)
- ruff check .: All checks passed. mypy src/: no issues in 106 source files. Full-suite pytest not re-run by me beyond the targeted files above.

## Per-story verdicts
- E5-S1: PASS (API checks and targeted pytest above)
- E5-S2: PASS (API checks and targeted pytest above)
- E5-S3: PASS (API checks and targeted pytest above)
- E5-S5: PASS (API checks and targeted pytest above)

## Not run / limitations
- Playwright/design layers: the contract has none; UI features are covered by the committed Playwright e2e suite (e2e/, 14 mocked tests) and are NOT live-verified by me. No Playwright MCP was used.
- Coverage gate not run (--no-cov).
- Architecture, trigger, append-only and migration-seed checks are proven by pytest only, not live.
- Uploaded content was a few synthetic bytes with real signatures (%PDF-, FFD8FF, 89504E47...) named per the classification stub fixtures.

## Notes
- Reports ran last on a small dataset (funnel: 11 INITIATED, 8 DOCS_SUBMITTED, 5 MANUAL_REVIEW, 4 APPROVED, 1 REJECTED). No payload contained the contact 9999999921 or any 'Test Person' name (F166 PII check).
- The analyst token also returns 403 on all 7 report endpoints (extra).
- S5-API-20: with product=NRE the funnel INITIATED count was 1 (only the Delta NRE case); filters echoed exactly.
- F155/F156 (50-case fixture, no float in metrics), F165 (p95 < 500 ms on 1,000 cases) and F172-F177 are proven only by pytest (counts above), not live.
- E5-S4 dashboard UI features F167-F171 are excluded from the contract and were not evaluated.

## features.json
- All features in this sprint contract's features list set passes=true with last_evaluated set and failure_reason/failure_layer null. UI features outside the contract were left untouched.
