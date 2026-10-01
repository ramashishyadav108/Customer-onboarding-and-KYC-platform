"""NFR-04 / NFR-08 / E1-S2 AC3: layering rules enforced by AST scans of the source tree."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "onboardx"
LAYERS = ["domain", "config", "repositories", "services", "controllers"]


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def modules(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def offenders(layer: str, forbidden: tuple[str, ...]) -> list[str]:
    bad: list[str] = []
    for path in modules(layer):
        for name in imports(path):
            if any(name == f or name.startswith(f + ".") for f in forbidden):
                bad.append(f"{path.relative_to(SRC)} imports {name}")
    return bad


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("layer", LAYERS[:-1])
def test_nfr04_lower_layers_never_import_higher_layers(layer: str) -> None:
    """Layers flow one way: controllers > services > repositories > config > domain."""
    higher = tuple(f"onboardx.{name}" for name in LAYERS[LAYERS.index(layer) + 1 :])
    assert offenders(layer, higher) == []


@pytest.mark.nfr("NFR-04")
def test_nfr04_domain_is_pure() -> None:
    """Domain imports no framework, persistence, JWT or I/O-library module."""
    banned = ("sqlalchemy", "fastapi", "starlette", "pydantic", "alembic", "jwt", "httpx",
              "requests", "onboardx.config", "onboardx.repositories")  # fmt: skip
    assert offenders("domain", banned) == []


@pytest.mark.nfr("NFR-04")
def test_nfr04_services_and_config_do_not_touch_web_or_orm_frameworks() -> None:
    """Services and config never import fastapi, starlette, sqlalchemy or alembic."""
    banned = ("fastapi", "starlette", "sqlalchemy", "alembic")
    assert offenders("services", banned) == []
    assert offenders("config", banned) == []


@pytest.mark.nfr("NFR-04")
def test_nfr04_only_repositories_use_sqlalchemy() -> None:
    """SQLAlchemy is confined to onboardx.repositories."""
    for layer in ("domain", "config", "services", "controllers"):
        assert offenders(layer, ("sqlalchemy",)) == []


@pytest.mark.nfr("NFR-04")
def test_nfr04_no_service_or_repository_imports_the_auth_dependency_module() -> None:
    """E1-S2 AC3: role checks live in controller dependencies only."""
    forbidden = ("onboardx.controllers",)
    assert offenders("services", forbidden) == []
    assert offenders("repositories", forbidden) == []


@pytest.mark.nfr("NFR-04")
def test_nfr04_role_enforcement_exists_only_in_controllers() -> None:
    """NFR-04: no service/repository code references require_role or Depends."""
    for layer in ("services", "repositories", "domain"):
        for path in modules(layer):
            text = path.read_text(encoding="utf-8")
            assert "require_role" not in text and "Depends(" not in text, path.name


@pytest.mark.nfr("NFR-04")
def test_nfr04_every_non_public_route_declares_a_role_dependency() -> None:
    """NFR-04: only /health, login and POST /leads are public; all else requires auth."""
    from fastapi.routing import APIRoute

    from onboardx.config.settings import Settings
    from onboardx.main import create_app

    app = create_app(Settings(_env_file=None, database_url="sqlite://", jwt_secret="x" * 40))  # type: ignore[call-arg]
    public = {("GET", "/health"), ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/leads")}
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path.startswith(
            ("/docs", "/openapi", "/redoc")
        ):
            continue
        names = {d.call.__name__ for d in route.dependant.dependencies}  # type: ignore[union-attr]
        for method in route.methods:
            if (method, route.path) in public:
                continue
            assert names & {"dependency", "require_case_access", "require_case_owner"}, (
                method, route.path,
            )  # fmt: skip


@pytest.mark.nfr("NFR-08")
def test_nfr08_only_the_transition_service_calls_update_state() -> None:
    """NFR-08: CaseRepository.update_state is reachable only from OnboardingService."""
    callers = []
    for layer in ("services", "controllers", "domain"):
        for path in modules(layer):
            if ".update_state(" in path.read_text(encoding="utf-8"):
                callers.append(path.name)
    assert callers == ["onboarding_service.py"]


@pytest.mark.nfr("NFR-02")
def test_nfr02_repositories_issue_no_update_or_delete_on_append_only_tables() -> None:
    """NFR-02: append-only repositories contain no UPDATE/DELETE statement constructs."""
    for name in ("state_history_repository", "audit_repository", "idempotency_repository"):
        text = (SRC / "repositories" / f"{name}.py").read_text(encoding="utf-8")
        assert "update(" not in text and "delete(" not in text
        assert "UPDATE" not in text and "DELETE" not in text


@pytest.mark.nfr("NFR-03")
def test_nfr03_source_contains_no_print_calls_or_logged_request_bodies() -> None:
    """NFR-03: no print() in the package; loggers never receive request bodies."""
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "print", path.name
