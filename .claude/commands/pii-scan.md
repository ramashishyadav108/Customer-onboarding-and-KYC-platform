---
name: pii-scan
description: Scan source and sample logs for plaintext PII (PAN, Aadhaar, contact, income, occupation) per NFR-03.
---

# /pii-scan

1. Grep `backend/src` for logger calls (`logger.`, `logging.`, `print(`) whose arguments include pan, aadhaar, phone, email, income, occupation, date_of_birth or full-name variables.
2. Check `backend/src/config/redaction.py` covers those keys.
3. If a log file or test output exists, grep it for PAN (`[A-Z]{5}[0-9]{4}[A-Z]`) and 12-digit Aadhaar patterns.
4. Report findings to `specs/reviews/pii-scan.md`. Any finding fails the scan.
