"""NFR-07: concurrent reads on the in-memory database (the default local run) never fail or tear."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_helpers import staff_headers
from helpers import JWT_SECRET
from onboardx.config.settings import Settings
from onboardx.main import create_app
from onboardx.repositories.database import create_db_engine, upgrade_to_head
from pipeline_helpers import submitted_case


@pytest.fixture
def memory_client(tmp_path: Path) -> Iterator[TestClient]:
    """The app exactly as `run_backend.py` builds it for DATABASE_URL=sqlite:///:memory:."""
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url="sqlite:///:memory:",
        jwt_secret=JWT_SECRET,
        upload_dir=tmp_path / "uploads",
    )
    engine = create_db_engine(settings.database_url)
    upgrade_to_head(engine)
    with TestClient(create_app(settings, engine)) as client:
        yield client
    engine.dispose()


@pytest.mark.nfr("NFR-07")
def test_nfr07_parallel_evidence_and_case_reads_all_succeed_on_in_memory_sqlite(
    memory_client: TestClient,
) -> None:
    """The staff console fires evidence + case reads at once; a shared SQLite connection used to
    return half-read rows (AttributeError -> 500) when two worker threads interleaved."""
    lead = submitted_case(memory_client)
    case = f"/api/v1/cases/{lead['case_id']}"
    staff = staff_headers(memory_client)

    def read(path: str) -> int:
        return memory_client.get(path, headers=staff).status_code

    paths = [f"{case}/evidence", case, f"{case}/documents", f"{case}/evidence"] * 25
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(read, paths))
    assert statuses == [200] * len(paths)
