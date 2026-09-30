# frontend

React + TypeScript + Vite. Dev server on :3000, proxy `/api` to :8000.

- Prospect portal is responsive (mobile first); staff workbench and admin console are desktop first. WCAG 2.1 AA.
- Mockups in `specs/design/mockups/`; field names must match `specs/design/api-contracts.schema.json`.
- Tests: Vitest for units, Playwright for E2E (`e2e/`, snapshots committed).
