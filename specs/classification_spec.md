# Risk Classification Spec

Stories: E3-S2, E3-S3 (primary), E3-S4, E3-S5, E5-S5. Features: F085-F099, F100-F113, F172-F177.

## Purpose
A versioned, integer-only rule engine maps an applicant profile to LOW, MEDIUM or HIGH. Published versions never change.

## Formula (fixed-point, no floats)
`score = (sum over factors of points[factor] * weight[factor]) // 100`, where weights are whole percentages summing to 100 and points are integers 0-100. Score is an int in 0..100.

## Proposed rule set v1 (for review)
Weights: age 20, income_band 25, occupation_category 30, geography 25.
Thresholds: LOW 0 to 29 (`low_max` 29), MEDIUM 30 to 59 (`medium_max` 59), HIGH 60 to 100.

| Factor | Value | Points |
|---|---|---|
| age (years at classification) | under 18 | 100 |
| | 18-24 | 30 |
| | 25-60 | 0 |
| | 61 and over | 40 |
| income_band (annual INR) | B1 under 500,000 | 10 |
| | B2 500,000-2,499,999 | 0 |
| | B3 2,500,000-9,999,999 | 30 |
| | B4 10,000,000 and over | 60 |
| occupation_category | SALARIED | 0 |
| | RETIRED, STUDENT | 10 |
| | SELF_EMPLOYED | 30 |
| | BUSINESS_OWNER | 50 |
| | CASH_INTENSIVE | 80 |
| geography (from country_code via static map) | DOMESTIC (IN) | 0 |
| | FOREIGN_STANDARD | 30 |
| | DOMESTIC_BORDER (country_code IN and state_code in the seeded synthetic border-state list JK, PB, AS) | 40 |
| | FOREIGN_HIGH_RISK | 100 |

Worked examples (used as tests):
- Age 35 (0), income 3,000,000 B3 (30), SELF_EMPLOYED (30), IN (0): 0*20 + 30*25 + 30*30 + 0*25 = 1650, 1650 // 100 = 16, LOW.
- Age 65 (40), 12,000,000 B4 (60), BUSINESS_OWNER (50), FOREIGN_STANDARD (30): 800 + 1500 + 1500 + 750 = 4550, score 45, MEDIUM.
- Age 65 (40), 12,000,000 B4 (60), CASH_INTENSIVE (80), FOREIGN_HIGH_RISK (100): 800 + 1500 + 2400 + 2500 = 7200, score 72, HIGH.

## Endpoints (provisional)
| Method and path | Role | Result |
|---|---|---|
| POST /api/v1/cases/{id}/classify | kyc-analyst, admin | SCREENED to CLASSIFIED; returns score, band, rule_version |
| GET/POST/PUT /api/v1/admin/rule-sets, POST .../publish | admin | draft, edit draft, publish |
| POST /api/v1/cases/{id}/reclassify | compliance-officer | new assessment with reason (see manual-review spec) |

## Acceptance Criteria

### AC-06 Versioned rule engine (age, income band, occupation category, geography) gives LOW/MEDIUM/HIGH; published rule versions are immutable
- AC-06.1 RuleSet has an int version, DRAFT or PUBLISHED status, integer weights, points tables, income band boundaries and integer thresholds.
- AC-06.2 Float or Decimal values are rejected with a ValidationError (API 422); static scan finds no float usage in risk modules (NFR-01).
- AC-06.3 Publishing sets PUBLISHED and `published_at`; any later update or delete raises PublishedRuleSetImmutableError and is blocked by a database trigger (API 409 RULESET_IMMUTABLE).
- AC-06.4 A new version is a DRAFT copy with version = max + 1; old versions stay readable.
- AC-06.5 Publish fails with RULESET_INVALID unless weights sum to 100 and thresholds ascend strictly.
- AC-06.6 Seeded v1 equals the values above.
- AC-06.7 The three worked examples score 16 LOW, 45 MEDIUM, 72 HIGH; boundaries 29 LOW, 30 MEDIUM, 59 MEDIUM, 60 HIGH.
- AC-06.8 Score is always an int in 0..100 (property test, 1,000 profiles).
- AC-06.9 Each evaluation appends a RiskAssessment with rule_version and per-factor breakdown; publishing a later version changes no stored assessment.
- AC-06.10 Classify moves SCREENED to CLASSIFIED; other states return 409 INVALID_STATE; a missing profile field returns 422 MISSING_PROFILE_FIELD.
- AC-06.11 Admin UI shows PUBLISHED versions read-only and DRAFT versions editable.

## Non-functional notes
NFR-01, NFR-05 (seed migration append-only), NFR-08 (immutability test E5-S5).
