# Fix loop 001: upload content validation (VULN-003 / VULN-004)

Branch: `fix/upload-content-validation`. Spec: AC-02.4a (added in the test commit, spec first).

## 1. Detection (red)
Commit `49a69a4` (`test:`) adds `backend/tests/integration/test_upload_content_validation.py` and spec line AC-02.4a. On main code: 6 failed, 3 passed.

```
FAILED test_ac02_4a_html_declared_as_an_allowed_type_is_415_and_not_stored[pan_valid.png-image/png]
>       assert response.status_code == 415
E       assert 201 == 415
```
(All 6 failures are 201 where 415 is required: 3 HTML payloads declared as png/jpg/pdf, 3 real content of another type.)

## 2. Reproduction (live, throwaway instance on port 8011, temp DB, before the fix)
```
POST upload pan_valid.png (image/png) body=b'<html><script>alert(1)</' -> 201 {"document_id":"a1ba5e95-2073-4f83-98a5-8f7bd9a923ca","checklist_item":"ID_PROOF","version":1,"doc_class":"PAN","status":"VERIFIED","reason_code":null,"confidence_bp":9500,"rule_vers
POST upload pan_valid.png (image/png) body=b'\x89PNG\r\n\x1a\n synthetic fixtu' -> 201 {"document_id":"08e5d210-f1f2-49be-987b-b9438e1c6380","checklist_item":"ID_PROOF","version":2,"doc_class":"PAN","status":"VERIFIED","reason_code":null,"confidence_bp":9500,"
POST upload pan_valid.pdf (application/pdf) body=b'%PDF-1.4 synthetic fixtu' -> 201 {"document_id":"257e1a4b-8ffd-4d13-9b50-a41a1537bd36","checklist_item":"ID_PROOF","version":3,"doc_class":"PAN","status":"VERIFIED","reason_code":null,"confidence_bp":9500,"rul
```
The first line is the defect: HTML bytes as `pan_valid.png` with Content-Type image/png returned 201.

## 3. Root cause
`backend/src/onboardx/domain/documents.py:41-52` (`validate_upload`) trusted the client Content-Type and the filename extension only; `controllers/routers/documents.py:40` read the body and passed it on with no content check. No magic-byte verification existed anywhere.

## 4. Fix
- `domain/documents.py`: pure `validate_content(kind, content)` (PDF `%PDF-`, JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`); mismatch raises `UnsupportedMediaTypeError` (415).
- `services/document_service.py`: called after type/extension/size/empty checks and before anything is stored, so a rejected upload writes no file and no row.
- Commit `944eb25`: 7 files, +78/-12. Commit `48c266a`: seed script `scripts/seed_demo_cohort.py` sent PDF bytes under .jpg names; found by the full suite and fixed with signature-valid bytes.
- Test helper changes (justified): `tests/pipeline_helpers.py` now derives synthetic bytes from the filename extension (previously PDF bytes for every type, invalid for jpg/png); fixtures `b"x"` (services_direct, concurrency) and `b"%PDF synthetic..."` (no dash) became PDF-signature bytes; the exact-5-MiB test pads a PDF header. The oversize (413) test is unchanged because size is checked before content.
- New unit tests: `tests/unit/test_upload_signatures.py`.

### VULN-004 (size cap): not fully fixable cleanly
The handler already reads at most 5 MiB + 1 byte (`file.read(MAX_UPLOAD_BYTES + 1)`) and returns 413 without storing. However FastAPI/Starlette parses and spools the entire multipart body before the handler runs, so a hard stop mid-stream needs a body-size middleware or reverse-proxy limit (Content-Length plus streaming counter), which touches app wiring and is out of scope here. VULN-004 stays open; recommended mitigation is a proxy limit (about 6 MiB on the upload route).

## 5. Validation (green)
- New tests: 9 integration + 16 unit, all pass. Existing document/upload tests, architecture tests: pass.
- Full suite with coverage: 1317 passed, 1 skipped, 0 failed; coverage 98% (gate 90%).
- ruff check, ruff format, mypy src, lint-imports (5 contracts kept): clean.
- Live re-probe on 8011 after the fix:
```
POST upload pan_valid.png (image/png) body=b'<html><script>alert(1)</' -> 415 {"error":{"code":"UNSUPPORTED_MEDIA_TYPE","message":"Unsupported file type","details":{"allowed":["pdf","jpg","png"]}}}
POST upload pan_valid.png (image/png) body=b'\x89PNG\r\n\x1a\n synthetic fixtu' -> 201 {"document_id":"35122269-0f02-45ee-9ef7-af8f5bd5ab2f","checklist_item":"ID_PROOF","version":1,"doc_class":"PAN","status":"VERIFIED","reason_code":null,"confidence_bp":9500,"
POST upload pan_valid.pdf (application/pdf) body=b'%PDF-1.4 synthetic fixtu' -> 201 {"document_id":"ca04d0ab-8378-43c4-b182-f2c92ae611a5","checklist_item":"ID_PROOF","version":2,"doc_class":"PAN","status":"VERIFIED","reason_code":null,"confidence_bp":9500,"rul
```
HTML-as-PNG is now 415 and valid PNG and PDF fixtures still return 201. The 8011 instance and its temp files were removed.

## 6. PR / merge
Merged with `git merge --no-ff fix/upload-content-validation` into main; the merge commit is the tip of main after this branch (see `git log --merges -1`).

## Knowledge deposit
Never trust client-declared upload metadata (Content-Type, extension). Declared type, extension and actual bytes must agree, checked by a pure domain function before any I/O, with a test that uploads a payload whose bytes contradict its declared type and asserts nothing is stored. Test fixtures must carry realistic signatures so validators can be strict without test-only escape hatches.
