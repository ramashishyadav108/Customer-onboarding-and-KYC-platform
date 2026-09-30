# Document Checklist and Upload Spec

Stories: E1-S5, E2-S1, E2-S2, E2-S4, E2-S5. Features: F036-F054, F062-F074.

## Checklists (v1, seeded by migration)
| Item | Savings | Current | NRE | Accepted classes |
|---|---|---|---|---|
| ID_PROOF | mandatory | mandatory | mandatory | PAN, AADHAAR, PASSPORT (NRE: PASSPORT only) |
| ADDRESS_PROOF | mandatory | mandatory | mandatory | AADHAAR, PASSPORT, UTILITY_BILL |
| PHOTOGRAPH | mandatory | mandatory | mandatory | PHOTOGRAPH |
| BUSINESS_PROOF | - | mandatory | - | GST_CERTIFICATE |
| OVERSEAS_ADDRESS_PROOF | - | - | mandatory | VISA |

## Endpoints (provisional)
| Method and path | Role | Result |
|---|---|---|
| GET /api/v1/products/{product}/checklist | any authenticated | version and items; 404 unknown product |
| POST /api/v1/cases/{id}/documents | owning prospect | 201 document_id, version, classification |
| GET /api/v1/cases/{id}/documents | owner, staff | current version per item |
| POST /api/v1/cases/{id}/submit | owning prospect | 200 DOCS_SUBMITTED, or 422 MISSING_DOCUMENTS / MISSING_PROFILE |
| POST /api/v1/cases/{id}/documents/{doc_id}/reject | kyc-analyst | 200 REJECTED |

## Acceptance Criteria

### AC-02 Upload KYC documents per product checklist; missing documents block submission
- AC-02.1 Savings, Current and NRE checklists contain exactly the items in the table above, with their accepted classes.
- AC-02.2 The checklist endpoint returns version and items; an unknown product returns 404.
- AC-02.3 A case keeps the checklist version it was created under after a newer version is seeded (append-only migration).
- AC-02.4 Upload accepts PDF, JPG, PNG up to 5 MB (415 and 413 otherwise) and only items on the case's product checklist (422 UNKNOWN_CHECKLIST_ITEM).
- AC-02.5 Stored documents record SHA-256, size and a sanitised filename; traversal names cannot escape the upload directory; content and names are never logged.
- AC-02.6 Submit with every mandatory item uploaded and the profile complete returns 200 and DOCS_SUBMITTED.
- AC-02.7 Submit with any mandatory item missing returns 422 MISSING_DOCUMENTS listing the missing item codes; state stays INITIATED.
- AC-02.8 Incomplete profile returns 422 MISSING_PROFILE.
- AC-02.9 Duplicate submit is idempotent; submit in any later state returns 409 INVALID_STATE.

### AC-09 (re-upload part) Prospect can re-upload missing or rejected documents without restarting
- AC-09.3a A kyc-analyst can reject a document with a reason code; other roles get 403.
- AC-09.3b While INITIATED, DOCS_SUBMITTED or MANUAL_REVIEW, re-upload creates version n+1; the earlier version is kept and marked superseded.
- AC-09.3c Re-upload leaves case_id, state and state history unchanged; on APPROVED or REJECTED it returns 409 CASE_LOCKED.
- AC-09.3d A replacement is classified again and clears `action_required` when VERIFIED.
- AC-09.3e GET case lists `action_required` items (MISSING, FLAGGED, REJECTED) with reason codes.
- AC-09.3f UI: upload page shows per-item status chips, gates Submit on mandatory items, supports in-place re-upload, meets WCAG 2.1 AA.

## Non-functional notes
NFR-02 documents append-only (new versions, never overwrite), NFR-03, NFR-05 (checklist migrations append-only).
