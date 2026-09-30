# Document Classification Stub Spec

Stories: E2-S3 (primary), E2-S1, E3-S5. Features: F055-F061.

## Purpose
Deterministic, no-OCR classifier for tests and demos. Class is decided by file-name prefix. Rules are rows in a migration-seeded table (versioned, append-only).

## Rule table (rule_version 1)
| File name prefix | doc_class | status | confidence_bp |
|---|---|---|---|
| pan_ | PAN | VERIFIED | 9500 |
| aadhaar_ | AADHAAR | VERIFIED | 9500 |
| passport_ | PASSPORT | VERIFIED | 9500 |
| utility-bill_ | UTILITY_BILL | VERIFIED | 9500 |
| photograph_ | PHOTOGRAPH | VERIFIED | 9500 |
| gst-certificate_ | GST_CERTIFICATE | VERIFIED | 9500 |
| visa_ | VISA | VERIFIED | 9500 |
| anything else | UNRECOGNISED | FLAGGED | 0 |

Extensions pdf, jpg, png. Matching is case-insensitive on the prefix. The first four rows are the brief's fixtures; the last three are proposed additions so Current and NRE cases can complete.

## Result shape
`{document_id, doc_class, status, reason_code|null, confidence_bp (int), rule_version, classified_at}`. Reason codes: DOC_UNRECOGNISED, DOC_CLASS_MISMATCH.

## Acceptance Criteria

### AC-03 Stubbed classification returns canned results for known fixtures and flags unrecognised files
- AC-03.1 `pan_valid.pdf`, `aadhaar_valid.jpg`, `passport_valid.png`, `utility-bill_valid.pdf` return PAN, AADHAAR, PASSPORT, UTILITY_BILL, status VERIFIED, confidence_bp 9500.
- AC-03.2 `photograph_*`, `gst-certificate_*`, `visa_*` return their classes with VERIFIED.
- AC-03.3 An unmatched name returns UNRECOGNISED, FLAGGED, reason DOC_UNRECOGNISED.
- AC-03.4 A recognised class not accepted by the target checklist item (for example utility-bill uploaded as ID_PROOF) returns FLAGGED, DOC_CLASS_MISMATCH.
- AC-03.5 Results are deterministic and confidence is an int.
- AC-03.6 Every classification is appended as a new row; UPDATE and DELETE are rejected by the database.
- AC-03.7 Rules are seeded by migration and only changed by a new migration (migration guard in E1-S1 fails on edits).
- AC-03.8 The stub makes no network call and reads no file content.
- AC-03.9 Staff UI shows class, status and reason code per document.

## Fixtures
`tests/fixtures/documents/` holds small synthetic files named per the table (valid and unrecognised). No real identifiers.

## Non-functional notes
NFR-02, NFR-05, NFR-03 (filenames never logged).
