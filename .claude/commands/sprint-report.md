---
name: sprint-report
description: Summarise the current sprint - contract status, evaluator verdict, ratchet scores, open failures.
---

# /sprint-report

1. Read `sprint-contracts/*.json`, `specs/reviews/`, `features.json`, `claude-progress.txt` and `.claude/state/iteration-log.md`.
2. Report groups completed and remaining, features passing / total, coverage vs baseline, last evaluator verdict and open learned rules.
3. Append a dated entry to `docs/sprint-log.md` (evidence trail for the rubric).
