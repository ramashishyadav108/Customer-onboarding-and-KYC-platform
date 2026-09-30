---
name: archtest-author
description: Authors architecture tests and import-linter contracts for OnboardX layering and immutability rules (NFR-08). Use when adding structural tests.
---

# archtest-author

Layering (one-way): controllers > services > repositories > config > domain. Domain is pure.
Contracts come from `specs/design/folder-structure.md`. Structural tests live in `tests/architecture/`.

## Required structural tests (at least 3; aim for all)
1. import-linter layers contract passes (`lint-imports`).
2. `domain` imports nothing from services, repositories, controllers or SQLAlchemy.
3. SQLAlchemy is imported only under `repositories`.
4. Published classification rule sets cannot be mutated (NFR-08).
5. An approved case cannot be modified (NFR-08).
6. Risk-band reassignment without an override audit record is refused (NFR-08).
7. No `float` in scoring modules (NFR-01).

Each test names the rule it enforces in its docstring and is tagged with the NFR id.
