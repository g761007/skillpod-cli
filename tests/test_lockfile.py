"""Tests for the lockfile capability.

Scenarios trace to
`openspec/changes/add-skillpod-mvp-install/specs/lockfile/spec.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skillpod import lockfile
from skillpod.lockfile import LockedSkill, Lockfile, LockfileError, hash_directory

_GOOD_COMMIT = "a" * 40
_GOOD_SHA = "b" * 64


def _entry(**overrides: object) -> LockedSkill:
    base = {
        "source": "git",
        "url": "https://github.com/example/skills",
        "commit": _GOOD_COMMIT,
        "sha256": _GOOD_SHA,
    }
    base.update(overrides)
    return LockedSkill(**base)  # type: ignore[arg-type]


# ---- Round-trip & ordering --------------------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    """Scenario: Lockfile after first install (read/write fidelity)."""
    p = tmp_path / "skillfile.lock"
    original = Lockfile(resolved={"audit": _entry(), "polish": _entry(commit="c" * 40)})
    lockfile.write(p, original)
    reloaded = lockfile.read(p)
    assert reloaded == original


def test_skill_field_order_is_canonical(tmp_path: Path) -> None:
    p = tmp_path / "skillfile.lock"
    lockfile.write(p, Lockfile(resolved={"audit": _entry()}))
    text = p.read_text(encoding="utf-8")
    # Field order: source, url, commit, sha256
    src_idx = text.index("source:")
    url_idx = text.index("url:")
    cmt_idx = text.index("commit:")
    sha_idx = text.index("sha256:")
    assert src_idx < url_idx < cmt_idx < sha_idx


def test_skill_keys_emitted_sorted(tmp_path: Path) -> None:
    p = tmp_path / "skillfile.lock"
    lockfile.write(
        p,
        Lockfile(
            resolved={
                "polish": _entry(commit="b" * 40),
                "audit": _entry(commit="a" * 40),
            }
        ),
    )
    text = p.read_text(encoding="utf-8")
    assert text.index("audit:") < text.index("polish:")


def test_no_registry_field_persisted(tmp_path: Path) -> None:
    """Scenario: Registry-resolved skill locks to git only.

    The schema does not even have a `registry` field; verify the file
    never contains the substring.
    """
    p = tmp_path / "skillfile.lock"
    lockfile.write(p, Lockfile(resolved={"audit": _entry()}))
    text = p.read_text(encoding="utf-8")
    assert "registry" not in text


# ---- Local sources are not lockable ----------------------------------------


def test_local_source_rejected_by_model() -> None:
    """Scenario: Manifest with a local skill produces no lock entry.

    We enforce this by typing `source` as Literal["git"]; constructing a
    LockedSkill with source="local" must fail.
    """
    with pytest.raises(Exception):  # pydantic.ValidationError
        LockedSkill(
            source="local",  # type: ignore[arg-type]
            url="/tmp/fake",
            commit=_GOOD_COMMIT,
            sha256=_GOOD_SHA,
        )


# ---- Validation -------------------------------------------------------------


def test_short_commit_rejected() -> None:
    with pytest.raises(Exception, match="commit"):
        _entry(commit="abc")


def test_non_hex_sha_rejected() -> None:
    with pytest.raises(Exception, match="sha256"):
        _entry(sha256="z" * 64)


# ---- Empty / missing lockfile ----------------------------------------------


def test_missing_file_returns_empty_lockfile(tmp_path: Path) -> None:
    sf = lockfile.read(tmp_path / "nope.lock")
    assert sf == Lockfile()
    assert sf.resolved == {}


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "skillfile.lock"
    p.write_text(":\n  - bad\n: yaml", encoding="utf-8")
    with pytest.raises(LockfileError, match="invalid YAML"):
        lockfile.read(p)


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    p = tmp_path / "skillfile.lock"
    p.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(LockfileError, match="mapping"):
        lockfile.read(p)


# ---- hash_directory --------------------------------------------------------


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
