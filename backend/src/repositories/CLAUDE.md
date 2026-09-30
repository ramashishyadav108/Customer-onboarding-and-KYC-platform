# backend/src/repositories

The only place SQLAlchemy / SQL is allowed.

- Append-only tables (documents, screening results, decisions, overrides, state history, rule versions, watchlist): insert and select only.
- Migrations live in `backend/migrations/versions/` and are never edited after creation.
- Return domain types, not ORM objects, to services.
