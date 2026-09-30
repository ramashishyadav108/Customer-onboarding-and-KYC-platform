---
name: risk-classifier
description: Rules for implementing and testing OnboardX risk-band classification (AC-06, NFR-01, NFR-08). Use when touching classification rules, scoring or bands.
---

# risk-classifier

Source of truth: `specs/classification_spec.md`.

## Rules
- Score = integer sum of (points x weight), integer-divided by 100. **No float, and no `/` true division** anywhere in scoring (NFR-01). Use `//` and basis points.
- Weights: age 20, income 25, occupation 30, geography 25. Bands: LOW 0-29, MEDIUM 30-59, HIGH 60-100.
- Inputs: date_of_birth, annual_income, occupation_category, country_code + state_code (DOMESTIC_BORDER = IN and state in JK, PB, AS).
- Rule sets are **versioned and immutable once published** (AC-06, NFR-08). Changes = a new version row via an append-only migration; never UPDATE/DELETE a published version.
- Re-assigning a band requires an override audit record (NFR-08); the service must refuse otherwise.

## Test checklist (tag each test with its AC id)
- One test per band boundary (29/30, 59/60) and per factor branch.
- A test that a published rule set cannot be mutated (AC-06).
- A test that classification is deterministic for a fixed rule version.
- A test that the scoring modules contain no `float(` and no `/` division.

## Layer placement
Pure logic in `backend/src/domain/`; persistence in repositories; orchestration in services. Domain imports nothing from outer layers.
