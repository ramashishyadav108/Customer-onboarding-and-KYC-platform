---
name: watchlist-matcher
description: Rules for AML/PEP watchlist matching and screening-hit handling (AC-05, NFR-02). Use when touching screening.
---

# watchlist-matcher

Source of truth: `specs/screening_spec.md`.

## Rules
- Match the prospect name against the static watchlist after normalisation (case-fold, collapse whitespace, strip punctuation). Matching is deterministic.
- A hit records a screening result (append-only, NFR-02) with rule reference, reason code (`AML_HIT` / `PEP_HIT`), timestamp and case_id. Never log the raw name (NFR-03); log case_id only.
- Lifecycle: the hit is recorded at SCREENED; the case continues to CLASSIFIED; the decision step routes it to MANUAL_REVIEW with the reason code. Do not add a SCREENED -> MANUAL_REVIEW edge.
- Watchlist entries change only through append-only migrations (NFR-05). Synthetic data only.

## Test checklist
Exact hit, case/whitespace variants, near-miss non-hit, PEP vs AML code, no hit -> no hit result, result rows never updated (AC-05).
