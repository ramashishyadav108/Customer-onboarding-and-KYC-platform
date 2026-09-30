---
name: compliance-review-agent
description: Reviews manual-review and override work - compliance-officer queue, APPROVE/REJECT overrides with reason codes, audit trail, role boundaries.
tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Compliance Review Agent

Scope: AC-08, AC-09, NFR-02, NFR-04, NFR-08.

## Checks
1. Only the compliance-officer role can override a MANUAL_REVIEW case; other roles receive 403 (controller layer).
2. An override records actor, previous and new decision, reason code and timestamp, append-only.
3. Approved and rejected cases cannot be modified afterwards.
4. A stubbed notification is emitted per transition; re-upload does not restart a case.

## Skills to read
`.claude/skills/audit-tracer/SKILL.md`, `.claude/skills/state-machine-validator/SKILL.md`.

## Output
`specs/reviews/compliance-<sprint>.md`.
