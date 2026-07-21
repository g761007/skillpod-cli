"""Tests for platform-portable filesystem helpers."""

from __future__ import annotations

import stat
from pathlib import Path

from skillpod.fsutil import rmtree


def test_rmtree_removes_an_ordinary_tree(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "file.md").write_text("content", encoding="utf-8")

    rmtree(root)

    assert not root.exists()


def test_rmtree_removes_write_protected_content(tmp_path: Path) -> None:
    """Removing a materialised skill must not depend on it being writable.

    git marks everything under `.git/objects/` read-only, and skillpod copies
    whole repositories when a repo's root *is* the skill — so
    `skillpod global update`, which replaces the installed copy, was failing
    with WinError 5 on Windows.

    The read-only *directory* here is what makes this test meaningful on POSIX
    too: a read-only file inside a writable directory deletes fine there, but a
    read-only directory blocks unlinking its children on every platform. Both
    reach the same recovery path.
    """
    root = tmp_path / "repo"
    objects = root / ".git" / "objects"
    objects.mkdir(parents=True)
    obj = objects / "0e7a14"
    obj.write_text("packed", encoding="utf-8")
    obj.chmod(stat.S_IRUSR)
    objects.chmod(stat.S_IRUSR | stat.S_IXUSR)

    rmtree(root)

    assert not root.exists()
