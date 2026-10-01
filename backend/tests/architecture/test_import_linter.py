"""NFR-04 / NFR-03: import-linter contracts pass; report SQL selects no PII column."""

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.nfr("NFR-04")
def test_nfr04_lint_imports_passes() -> None:
    """All contracts (layers, domain purity, SQLAlchemy only in repositories) are kept."""
    result = subprocess.run(  # noqa: S603
        [str(Path(sys.executable).parent / "lint-imports")],
        cwd=BACKEND, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 broken" in result.stdout


@pytest.mark.nfr("NFR-03")
def test_nfr03_report_queries_never_select_pii_columns() -> None:
    """The report SQL module mentions no name, contact, profile or document column."""
    text = (BACKEND / "src/onboardx/repositories/report_queries.py").read_text(encoding="utf-8")
    sql = text.split("COHORT =")[1].split("def _start")[0].lower()
    for column in (
        "c.name",
        "contact",
        "annual_income",
        "date_of_birth",
        "display_name",
        "case_profiles",
    ):
        assert column not in sql, column
    assert "avg(" not in sql
