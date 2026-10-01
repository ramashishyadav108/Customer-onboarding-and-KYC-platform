"""NFR-01 / AC-06.2: static scan of the domain, services and repositories for float usage."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "onboardx"
SCANNED = [SRC / "domain", SRC / "services", SRC / "repositories"]
RISK_MODULES = [SRC / "domain" / "risk.py", SRC / "domain" / "ruleset_codec.py"]


def files(roots: list[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        found.extend([root] if root.is_file() else sorted(root.rglob("*.py")))
    return found


def violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Name) and node.id == "float":
            problems.append(f"{path.name}:{line} float name")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            problems.append(f"{path.name}:{line} float literal {node.value!r}")
        elif isinstance(node, ast.BinOp | ast.AugAssign) and isinstance(node.op, ast.Div):
            problems.append(f"{path.name}:{line} true division")
        elif isinstance(node, ast.Attribute) and node.attr in {"Decimal", "float"}:
            problems.append(f"{path.name}:{line} {node.attr} attribute")
    return problems


@pytest.mark.nfr("NFR-01")
@pytest.mark.ac("AC-06")
@pytest.mark.parametrize("path", files(RISK_MODULES), ids=lambda p: p.name)
def test_nfr01_risk_modules_have_no_float_type_literal_or_division(path: Path) -> None:
    """AC-06.2: the risk modules contain no float type, float literal or '/' division."""
    assert violations(path) == []


@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize("path", files(SCANNED), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_nfr01_no_float_anywhere_in_domain_services_repositories(path: Path) -> None:
    """NFR-01: no float type, literal, Decimal or true division in the business layers."""
    assert violations(path) == []


@pytest.mark.nfr("NFR-01")
def test_nfr01_scan_detects_violations(tmp_path: Path) -> None:
    """NFR-01: the scanner itself flags float(), float literals and '/'."""
    sample = tmp_path / "bad.py"
    sample.write_text("x = float('1')\ny = 0.5\nz = 3 / 2\nw = 1\nw /= 2\n", encoding="utf-8")
    kinds = " ".join(violations(sample))
    assert "float name" in kinds and "float literal" in kinds and "true division" in kinds
    assert len(violations(sample)) == 4


@pytest.mark.nfr("NFR-01")
def test_nfr01_migrations_declare_no_float_columns() -> None:
    """NFR-01: no migration mentions FLOAT, REAL, DOUBLE, NUMERIC or DECIMAL column types."""
    versions = SRC.parents[1] / "migrations" / "versions"
    banned = ("FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL")
    for path in versions.glob("0*.py"):
        text = path.read_text(encoding="utf-8").upper()
        assert not any(word in text for word in banned), path.name
