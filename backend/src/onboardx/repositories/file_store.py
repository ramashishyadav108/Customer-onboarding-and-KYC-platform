"""Traversal-safe local file store under a configurable upload directory (AC-02.5)."""

from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    """The relative path would leave the store root."""


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _resolve(self, relative_path: str) -> Path:
        pure = PurePosixPath(relative_path)
        unsafe = (
            not relative_path
            or "\\" in relative_path
            or "\x00" in relative_path
            or pure.is_absolute()
            or ".." in pure.parts
            or Path(relative_path).is_absolute()
            or Path(relative_path).drive != ""
        )
        if unsafe:
            raise UnsafePathError("path escapes the upload directory")
        root = self._root.resolve()
        target = root.joinpath(*pure.parts).resolve()
        if not target.is_relative_to(root):
            raise UnsafePathError("path escapes the upload directory")
        return target

    def save(self, relative_path: str, content: bytes) -> None:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def read(self, relative_path: str) -> bytes:
        return self._resolve(relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        self._resolve(relative_path).unlink(missing_ok=True)
