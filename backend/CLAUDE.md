# backend

Python 3.12 FastAPI service. Venv at `backend/.venv` (`python -m venv .venv`), dependencies in `pyproject.toml`, pinned in `requirements.lock`.

- Layers (one-way): controllers > services > repositories > config > domain. Enforced by import-linter and `tests/architecture/`.
- Integers only for scoring (NFR-01). No plaintext PII in logs (NFR-03). Structured JSON logs with correlation id and case_id (NFR-06).
- Append-only: documents, screening results, decisions, overrides, migrations (NFR-02, NFR-05).
- Tests: `.venv/Scripts/python -m pytest`, coverage via `pytest-cov` (writes `coverage.xml`). Tag every test with its AC/NFR id.
- Contracts: `specs/design/api-contracts.schema.json`, `specs/design/data-models.schema.json`.
