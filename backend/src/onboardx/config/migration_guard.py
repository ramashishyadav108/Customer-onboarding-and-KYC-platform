"""Migration guard: applied migrations are append-only (NFR-05).

Every migration file has a SHA-256 entry in a committed manifest. Editing or deleting a
registered file, or adding a file without a manifest entry, is a guard failure.
"""

import hashlib
import json
from pathlib import Path


class MigrationGuardError(Exception):
    """Raised when the migration files no longer match the committed manifest."""


def file_digest(path: Path) -> str:
    """SHA-256 of the file with line endings normalised so checkouts agree."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _migration_files(versions_dir: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(versions_dir.glob("*.py")) if p.name != "__init__.py"}


def _load_manifest(manifest_path: Path) -> dict[str, str]:
    data: dict[str, str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data


def _diff(versions_dir: Path, manifest: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    files = _migration_files(versions_dir)
    modified = [n for n, d in sorted(manifest.items()) if n in files and file_digest(files[n]) != d]
    deleted = [n for n in sorted(manifest) if n not in files]
    unregistered = [n for n in files if n not in manifest]
    return modified, deleted, unregistered


def verify_migrations(versions_dir: Path, manifest_path: Path) -> list[str]:
    """Return a list of human-readable problems; empty means the guard passes."""
    if not manifest_path.is_file():
        return [f"manifest missing: {manifest_path.name}"]
    modified, deleted, unregistered = _diff(versions_dir, _load_manifest(manifest_path))
    return (
        [f"modified migration: {name}" for name in modified]
        + [f"deleted migration: {name}" for name in deleted]
        + [f"unregistered migration: {name}" for name in unregistered]
    )


def assert_migrations_unmodified(versions_dir: Path, manifest_path: Path) -> None:
    problems = verify_migrations(versions_dir, manifest_path)
    if problems:
        raise MigrationGuardError("; ".join(problems))


def update_manifest(versions_dir: Path, manifest_path: Path) -> list[str]:
    """Register NEW migration files only; refuse when an existing entry would change."""
    manifest = _load_manifest(manifest_path) if manifest_path.is_file() else {}
    modified, deleted, unregistered = _diff(versions_dir, manifest)
    if modified or deleted:
        raise MigrationGuardError(
            "refusing to update manifest; existing migrations changed: "
            + ", ".join(modified + deleted)
        )
    files = _migration_files(versions_dir)
    for name in unregistered:
        manifest[name] = file_digest(files[name])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return unregistered
