# Reports and Admin Console Spec

Stories: E5-S1, E5-S2, E5-S3, E5-S4 (primary), E3-S5 (admin rule and watchlist pages). Features: F151-F171.

## Purpose
Give admins operational visibility derived only from append-only history (state history, decisions, overrides). Integers only: seconds for durations, basis points for ratios.

## Metrics
| Metric | Definition |
|---|---|
| TAT by product | For closed cases, seconds from INITIATED to APPROVED or REJECTED; count, avg, min, max per product |
| Approval funnel | Cases that ever reached INITIATED, DOCS_SUBMITTED, SCREENED, CLASSIFIED, final outcome; conversion_bp from previous stage |
| Manual-review backlog | Current MANUAL_REVIEW count, oldest age in minutes, buckets under 60, 60-1440, over 1440 minutes |
| Avg time per stage | Mean seconds between consecutive transitions, by from-state |
| Top rejection reasons | Five most frequent reason codes among REJECTED cases; count desc, code asc |
| Auto-approval rate | AUTO approved / decided, basis points, vs proposed target 6000 |

## Endpoints (provisional, admin only)
GET /api/v1/admin/reports/tat, /funnel, /backlog, /time-per-stage, /rejection-reasons, /auto-approval with optional `product`, `from`, `to` (ISO dates, inclusive).

## Acceptance Criteria

### AC-10 Admin views TAT by product, approval funnel, manual-review backlog, average time per stage, top rejection reasons
- AC-10.1 TAT by product is correct on a seeded fixture (count, avg, min, max in whole seconds); open cases are excluded.
- AC-10.2 Average time per stage uses consecutive transitions; open cases contribute completed stages only.
- AC-10.3 Funnel counts and conversion_bp match hand-computed values.
- AC-10.4 Backlog count, oldest age and buckets are correct.
- AC-10.5 Top rejection reasons returns at most five, ordered count desc then code asc.
- AC-10.6 Auto-approval rate is reported against the 6000 bp target with a met flag.
- AC-10.7 All metrics honour `product` and `from`/`to`; empty results return zeros; invalid filters return 422.
- AC-10.8 Endpoints return 401 without a token and 403 for non-admin roles; payloads contain no PII.
- AC-10.9 p95 latency under 500 ms at 1,000 synthetic cases.
- AC-10.10 Dashboard shows seven panels (the five metrics, auto-approval rate and dropped leads), filters refresh all panels, every chart has a table and text alternative, empty states are explicit, WCAG 2.1 AA, desktop-first, admin-only route.
- AC-10.11 Dropped-lead analysis (brief 6.2): `GET /api/v1/admin/reports/dropped-leads?older_than_days=7&product=` counts open INITIATED and DOCS_SUBMITTED cases with no activity for more than N days; admin only, no PII; shown as a dashboard panel with a table and text alternative.

## Non-functional notes
NFR-01 (no floats in metrics), NFR-04.
