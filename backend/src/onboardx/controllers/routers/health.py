"""GET /health: public, unversioned liveness probe (E1-S1 AC1)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
