"""NFR-05 / E1-S1 AC5: migration guard keeps applied migrations immutable (F008, F009)."""

import json
import shutil
from pathlib import Path

import pytest

from onboardx.config.migration_guard import (
    MigrationGuardError,
    assert_migrations_unmodified,
    update_manifest,
    verify_migrations,
)

REAL_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture
def migrations(tmp_path: Path) -> Path:
    target = tmp_path / "migrations"
    shutil.copytree(REAL_MIGRATIONS, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _paths(root: Path) -> tuple[Path, Path]:
    return root / "versions", root / "manifest.json"


def test_nfr05_guard_passes_on_committed_tree() -> None:
    """NFR-05 (F008): the committed migrations match the committed manifest."""
    versions, manifest = _paths(REAL_MIGRATIONS)
    assert verify_migrations(versions, manifest) == []
    assert_migrations_unmodified(versions, manifest)


def test_nfr05_editing_an_existing_migration_fails(migrations: Path) -> None:
    """NFR-05 (F008): editing an existing migration file makes the guard fail."""
    versions, manifest = _paths(migrations)
    target = next(versions.glob("0001_*.py"))
    target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    problems = verify_migrations(versions, manifest)
    assert any("modified" in p and target.name in p for p in problems)
    with pytest.raises(MigrationGuardError):
        assert_migrations_unmodified(versions, manifest)


def test_nfr05_deleting_a_migration_fails(migrations: Path) -> None:
    """NFR-05 (F008): deleting an existing migration file makes the guard fail."""
    versions, manifest = _paths(migrations)
    target = next(versions.glob("0002_*.py"))
    target.unlink()
    problems = verify_migrations(versions, manifest)
    assert any("deleted" in p and target.name in p for p in problems)
    with pytest.raises(MigrationGuardError):
        assert_migrations_unmodified(versions, manifest)


def test_nfr05_line_endings_do_not_change_the_hash(migrations: Path) -> None:
    """NFR-05: a checkout with CRLF line endings still passes the guard."""
    versions, manifest = _paths(migrations)
    target = next(versions.glob("0001_*.py"))
    target.write_bytes(target.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert verify_migrations(versions, manifest) == []


def test_nfr05_new_migration_with_new_manifest_entry_passes(migrations: Path) -> None:
    """NFR-05 (F009): a new file with a new manifest entry passes; old entries are unchanged."""
    versions, manifest = _paths(migrations)
    before = json.loads(manifest.read_text(encoding="utf-8"))
    (versions / "9001_test_addition.py").write_text("revision = '9001'\n", encoding="utf-8")
    assert any("9001_test_addition.py" in p for p in verify_migrations(versions, manifest))
    added = update_manifest(versions, manifest)
    assert added == ["9001_test_addition.py"]
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert {k: after[k] for k in before} == before
    assert verify_migrations(versions, manifest) == []


def test_nfr05_manifest_update_refuses_to_rewrite_existing_entries(migrations: Path) -> None:
    """NFR-05: the manifest updater never overwrites a hash for an edited migration."""
    versions, manifest = _paths(migrations)
    target = next(versions.glob("0001_*.py"))
    target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    with pytest.raises(MigrationGuardError):
        update_manifest(versions, manifest)


def test_nfr05_missing_manifest_fails(tmp_path: Path) -> None:
    """NFR-05: a missing manifest is a guard failure, not a pass."""
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "0001_x.py").write_text("x = 1\n", encoding="utf-8")
    assert verify_migrations(versions, tmp_path / "manifest.json") != []
