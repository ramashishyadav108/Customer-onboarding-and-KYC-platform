#!/bin/bash
set -euo pipefail

echo "=== Bootstrapping dev environment ==="

# Backend dependencies
[ -d backend/.venv ] || python -m venv backend/.venv; backend/.venv/Scripts/python -m pip install -r backend/requirements.lock -e "backend[dev]" 2>/dev/null || backend/.venv/bin/python -m pip install -r backend/requirements.lock -e "backend[dev]"

# Frontend dependencies
cd frontend && npm ci && cd ..

# Environment
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys"
fi

# Local mode: servers are started by the evaluator/orchestrator (no Docker)

# Health checks
echo "Waiting for services..."
curl -sf --retry 5 --retry-delay 2 --retry-connrefused http://localhost:8000/health || echo "backend not up yet"
curl -sf --retry 5 --retry-delay 2 --retry-connrefused http://localhost:3000 || echo "frontend not up yet"

echo "=== Environment ready ==="
