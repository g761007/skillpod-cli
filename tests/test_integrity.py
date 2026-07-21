"""Tests for content digests of materialised skill directories.

Split out of test_lockfile.py when integrity moved to skillpod.integrity —
hashing is consumed by fan-out and global install, not just the lockfile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skillpod.integrity import hash_directory


def test_hash_directory_is_stable(tmp_path: Path) -> None:
    skill = tmp_path / "audit"
    (skill / "nested").mkdir(parents=True)
    (skill / "manifest.json").write_text("{}", encoding="utf-8")
    (skill / "nested" / "tool.md").write_text("hello", encoding="utf-8")

    a = hash_directory(skill)
    b = hash_directory(skill)
    assert a == b
    assert len(a) == 64


def test_hash_directory_changes_with_content(tmp_path: Path) -> None:
    skill = tmp_path / "audit"
    skill.mkdir()
    (skill / "x").write_text("one", encoding="utf-8")
    h1 = hash_directory(skill)
    (skill / "x").write_text("two", encoding="utf-8")
    h2 = hash_directory(skill)
    assert h1 != h2


def test_hash_directory_changes_with_filename(tmp_path: Path) -> None:
    a = tmp_path / "a"
    a.mkdir()
    (a / "first").write_text("x", encoding="utf-8")
    h1 = hash_directory(a)

    b = tmp_path / "b"
    b.mkdir()
    (b / "second").write_text("x", encoding="utf-8")
    h2 = hash_directory(b)
    assert h1 != h2


def test_hash_directory_includes_symlink_target(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    target_a = tmp_path / "outside_a"
    target_a.write_text("ignored", encoding="utf-8")
    (skill / "lnk").symlink_to(target_a)
    h1 = hash_directory(skill)

    (skill / "lnk").unlink()
    target_b = tmp_path / "outside_b"
    target_b.write_text("ignored", encoding="utf-8")
    (skill / "lnk").symlink_to(target_b)
    h2 = hash_directory(skill)

    assert h1 != h2


def test_hash_directory_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_directory(tmp_path / "nope")
