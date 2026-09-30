# backend/src/controllers

HTTP layer and authentication boundary (NFR-04).

- Roles: prospect, kyc-analyst, compliance-officer, admin. Every route declares `require_role(...)`; only `POST /leads` and `/health` are public.
- No business rules here; delegate to services.
- Add correlation-id middleware; responses never echo PII beyond what the contract defines.
