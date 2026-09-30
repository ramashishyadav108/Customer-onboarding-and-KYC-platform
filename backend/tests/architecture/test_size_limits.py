"""Code-quality gates: source files under 300 lines and functions under 50 lines."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "onboardx"
MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
FILES = sorted(SRC.rglob("*.py"))


@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SRC)))
def test_nfr08_source_files_are_shorter_than_300_lines(path: Path) -> None:
    assert len(path.read_text(encoding="utf-8").splitlines()) < MAX_FILE_LINES


@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SRC)))
def test_nfr08_functions_are_shorter_than_50_lines(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    too_long = [
        f"{node.name}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and (node.end_lineno or node.lineno) - node.lineno + 1 >= MAX_FUNCTION_LINES
    ]
    assert too_long == []


@pytest.mark.nfr("NFR-02")
def test_nfr02_new_append_only_repositories_issue_no_update_or_delete() -> None:
    """NFR-02: document, screening, assessment, decision and notification repositories only
    insert and select."""
    names = (
        "document_repository",
        "screening_repository",
        "assessment_repository",
        "decision_repository",
        "notification_repository",
    )
    for name in names:
        text = (SRC / "repositories" / f"{name}.py").read_text(encoding="utf-8")
        assert "update(" not in text and "delete(" not in text, name
        assert "UPDATE" not in text and "DELETE" not in text, name


@pytest.mark.nfr("NFR-04")
def test_nfr04_only_the_onboarding_service_writes_case_state() -> None:
    """NFR-08: decision, screening and risk services never write case state themselves."""
    for name in ("decision_service", "screening_service", "risk_service", "submission_service"):
        text = (SRC / "services" / f"{name}.py").read_text(encoding="utf-8")
        assert "update_state" not in text and "uow.cases.add" not in text, name
