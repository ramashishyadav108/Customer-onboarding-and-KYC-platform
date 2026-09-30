# tests

- `tests/architecture/`: structural tests (layering, immutability, no-float). Authored via `archtest-author-agent`.
- Every spec AC-NN and NFR-NN has at least one test whose name or docstring contains the id. Run `/ac-trace` to check.
- TDD: commit the failing test before the implementation (see `docs/tdd.md`).
- Synthetic data only.
