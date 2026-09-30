"""E2-S1 AC5 / AC-02.5: the file store cannot be made to touch anything outside its root."""

from pathlib import Path

import pytest

from onboardx.repositories.file_store import LocalFileStore, UnsafePathError


@pytest.mark.ac("AC-02")
def test_ac02_5_save_and_read_round_trip_creating_directories(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "uploads")
    store.save("case-1/doc-1.pdf", b"hello")
    assert store.read("case-1/doc-1.pdf") == b"hello"
    assert (tmp_path / "uploads" / "case-1" / "doc-1.pdf").read_bytes() == b"hello"


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    "path",
    [
        "../escape.pdf",
        "a/../../escape.pdf",
        "..",
        "/etc/passwd",
        "\\windows\\x.pdf",
        "a\\..\\b.pdf",
        "C:\\x.pdf",
        "C:/x.pdf",
        "",
        "a\x00b.pdf",
    ],
)
def test_ac02_5_unsafe_paths_are_refused_for_every_operation(tmp_path: Path, path: str) -> None:
    """AC-02.5: traversal, absolute, backslash, drive and NUL paths raise UnsafePathError."""
    store = LocalFileStore(tmp_path / "uploads")
    with pytest.raises(UnsafePathError):
        store.save(path, b"x")
    with pytest.raises(UnsafePathError):
        store.read(path)
    with pytest.raises(UnsafePathError):
        store.delete(path)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


@pytest.mark.ac("AC-02")
def test_ac02_5_a_symlink_pointing_outside_the_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this platform")
    with pytest.raises(UnsafePathError):
        LocalFileStore(root).save("link/evil.pdf", b"x")
    assert list(outside.iterdir()) == []


@pytest.mark.ac("AC-02")
def test_ac02_delete_removes_the_file_and_is_idempotent(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    store.save("c/d.pdf", b"x")
    store.delete("c/d.pdf")
    store.delete("c/d.pdf")
    assert not (tmp_path / "c" / "d.pdf").exists()


@pytest.mark.nfr("NFR-02")
def test_nfr02_documents_are_stored_under_unique_paths(tmp_path: Path) -> None:
    """Different document ids never overwrite each other."""
    store = LocalFileStore(tmp_path)
    store.save("c/d1.pdf", b"one")
    store.save("c/d2.pdf", b"two")
    assert (store.read("c/d1.pdf"), store.read("c/d2.pdf")) == (b"one", b"two")
