# TDD discipline

Every change follows red -> green -> refactor, driven by the agents under supervision (no hand-written production code).

1. **Red:** the test-first agent writes a failing test tagged with the AC/NFR id (`@pytest.mark.ac("AC-06")`, id in the test name). The failing test is committed on its own (`test:` commit) before any implementation.
2. **Green:** the generator writes the minimum code to pass; the commit is a `feat:` commit.
3. **Refactor:** clean-up with the test suite green (`refactor:` commit), subject to the hooks (function < 50 lines, file < 300 lines) and the architecture tests.
4. **Ratchet:** the evaluator verdict and the coverage baseline (`.claude/state/coverage-baseline.txt`, floor 80%) only move up.

## Worked example - AC-06 risk-band branch coverage
- **Spec:** `specs/classification_spec.md`: score = sum(points x weight) // 100; LOW 0-29, MEDIUM 30-59, HIGH 60-100.
- **Red:** parametrised tests for each band boundary (29/30, 59/60), every factor branch (age, income band, occupation, geography incl. the `DOMESTIC_BORDER` state branch) and the worked examples 16 -> LOW, 45 -> MEDIUM, 72 -> HIGH (`backend/tests/unit/test_risk_scoring.py`, `test_risk_ruleset.py`). They fail while `domain/risk.py` is absent.
- **Green:** integer-only `score` and `band_for_score` implementation in `domain/risk.py`.
- **Refactor:** extract factor lookups; `tests/architecture/test_no_float_scan.py` guards NFR-01 and `test_size_limits.py` guards function size.
- **Immutability (NFR-08):** tests prove a published rule set cannot be changed at the service, repository and database-trigger levels.

Run `/ac-trace` to confirm every AC/NFR id has at least one test.
