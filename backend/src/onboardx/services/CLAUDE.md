# backend/src/services

Orchestrates use cases by calling domain rules and repositories.

- No HTTP, FastAPI, `Depends`, `Request` or auth logic (NFR-04 boundary is the controller).
- Never UPDATE/DELETE append-only data; append a new row instead.
- Every state change goes through the domain transition function and appends a history row and a stubbed notification.
