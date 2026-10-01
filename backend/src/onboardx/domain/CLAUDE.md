# backend/src/domain

Pure business rules: state machine, risk scoring, watchlist matching, checklist resolution, document-classification stub.

- Imports nothing from services, repositories, controllers, config, SQLAlchemy or FastAPI.
- Integer / fixed-point arithmetic only (no `float`, no `/`).
- Raises `InvalidOnboardingStateException` for invalid transitions.
- Read `.claude/skills/risk-classifier`, `watchlist-matcher`, `state-machine-validator` before editing.
