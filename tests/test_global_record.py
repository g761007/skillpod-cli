"""Tests for the global install record and its backfill.

Phase 1c of `plans/2026-07-21-recommendation-model.md`. Recording what a global
install did is the prerequisite for `skillpod global update` — without it there
is nothing to re-resolve against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skillpod.installer.global_backfill import reconcile_global_record
from skillpod.installer.global_install import install_global, uninstall_global
from skillpod.installer.global_record import read_global_record, write_global_record
from skillpod.installer.paths import global_skill_dir
from skillpod.profile.snapshot import recover_source
from skillpod.record.models import InstallRecord, SkillRecord
from skillpod.sources.cache import cache_root
from skillpod.sources.discovery import discover_skills
from skillpod.sources.spec import parse_source_spec
from tests._git_fixtures import make_root_skill_repo

_COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))


def _install(source: str, home: Path, *, agents: list[str] | None = None) -> None:
    spec = parse_source_spec(source)
    assert spec is not None
    root = Path(spec.url_or_path)
    if spec.kind == "git":
        from skillpod.installer.global_install import populate_cache, resolve_ref

        root = populate_cache(spec.url_or_path, resolve_ref(spec.url_or_path, spec.ref or "main"))
    discovered = discover_skills(root, root_name=spec.derived_name)
    install_global(spec, discovered, agents=agents or ["claude"], force=True, home=home)


# ---- installing records what it did ----------------------------------------


def test_git_install_records_source_ref_and_commit(tmp_path: Path) -> None:
    """This is the prerequisite for `global update` to exist at all."""
    repo, sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    url = repo.as_uri()  # file:///C:/... on Windows, file:///... elsewhere

    _install(url, home)

    rec = read_global_record(home).installed["audit"]
    assert rec.kind == "git"
    assert rec.source == url
    assert rec.commit == sha
    assert rec.ref is not None
    assert rec.sha256 is not None


def test_local_install_is_recorded_without_a_commit(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"

    _install(str(repo), home)

    rec = read_global_record(home).installed["audit"]
    assert rec.kind == "local"
    assert rec.commit is None
    assert rec.sha256 is not None


def test_second_install_merges_rather_than_replaces(tmp_path: Path) -> None:
    """Installing one skill must not erase the record of the others."""
    audit, _ = make_root_skill_repo(tmp_path / "a", repo_name="audit")
    polish, _ = make_root_skill_repo(tmp_path / "b", repo_name="polish")
    home = tmp_path / "home"

    _install(str(audit), home)
    _install(str(polish), home)

    assert set(read_global_record(home).installed) == {"audit", "polish"}


def test_uninstall_forgets_the_skill(tmp_path: Path) -> None:
    """A record claiming a skill that is gone is worse than no record."""
    # A plain directory rather than a git repo: uninstall rmtree's the
    # materialised copy, and git's read-only object files make that fail on
    # Windows (see issue #10). Nothing here needs version control.
    pool = tmp_path / "pool" / "audit"
    pool.mkdir(parents=True)
    (pool / "SKILL.md").write_text("---\ndescription: audit\n---\n", encoding="utf-8")
    home = tmp_path / "home"
    _install(str(pool), home)

    uninstall_global("audit", agents=["claude"], home=home)

    assert "audit" not in read_global_record(home).installed


# ---- the record outranks symlink archaeology -------------------------------


def test_recover_source_prefers_the_record(tmp_path: Path) -> None:
    """Once recorded, provenance no longer depends on how the skill was
    materialised — which is what was broken before: `install_global` writes a
    real directory, and the old recovery could only read symlinks."""
    repo, sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    url = repo.as_uri()
    _install(url, home)

    # Materialised as a real directory, so symlink archaeology cannot help.
    assert global_skill_dir("audit", home).is_dir()
    assert not global_skill_dir("audit", home).is_symlink()

    recovered = recover_source("audit", home)
    assert recovered.source == url
    # The branch, not the commit it happened to point at on this machine.
    assert recovered.ref == "main"
    assert recovered.ref != sha


def test_recover_source_prefers_ref_over_commit(tmp_path: Path) -> None:
    """A saved profile should track the branch, not freeze at whatever commit
    happened to be current on the machine that saved it."""
    home = tmp_path / "home"
    write_global_record(
        InstallRecord(
            installed={
                "audit": SkillRecord(
                    kind="git", source="o/r", ref="main", commit=_COMMIT
                )
            }
        ),
        home,
    )
    assert recover_source("audit", home).ref == "main"


def test_recover_source_falls_back_to_commit_without_a_ref(tmp_path: Path) -> None:
    """Migrated entries have no ref; the commit is better than nothing."""
    home = tmp_path / "home"
    write_global_record(
        InstallRecord(
            installed={"audit": SkillRecord(kind="git", source="o/r", commit=_COMMIT)}
        ),
        home,
    )
    assert recover_source("audit", home).ref == _COMMIT


# ---- backfill for skills that predate the record ---------------------------


def test_backfill_recovers_a_cache_symlink(tmp_path: Path) -> None:
    """Legacy installs symlinked into the cache, which still encodes the
    owner/repo/commit — those are recoverable."""
    home = tmp_path / "home"
    cache_skill = cache_root() / "github.com" / "anthropics" / f"skills@{_COMMIT}" / "audit"
    cache_skill.mkdir(parents=True)
    link = global_skill_dir("audit", home)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(cache_skill)

    record, report = reconcile_global_record(home)

    assert report.recovered == ["audit"]
    assert record.installed["audit"].source == "anthropics/skills"


def test_backfill_marks_unrecoverable_skills_unknown(tmp_path: Path) -> None:
    """Measured on the author's machine: 37 of 88 global skills are real
    directories with no recoverable origin. Recording them as unknown is what
    lets `global update` report them instead of silently skipping them."""
    home = tmp_path / "home"
    global_skill_dir("mystery", home).mkdir(parents=True)

    record, report = reconcile_global_record(home)

    assert report.unknown == ["mystery"]
    assert record.installed["mystery"].kind == "unknown"
    assert record.installed["mystery"].source is None


def test_backfill_prunes_skills_deleted_by_hand(tmp_path: Path) -> None:
    home = tmp_path / "home"
    write_global_record(
        InstallRecord(
            installed={"ghost": SkillRecord(kind="git", source="o/r", commit=_COMMIT)}
        ),
        home,
    )

    record, report = reconcile_global_record(home)

    assert report.pruned == ["ghost"]
    assert record.installed == {}


def test_backfill_leaves_existing_entries_alone(tmp_path: Path) -> None:
    """Reconciling must not overwrite provenance that is already known."""
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    _install(str(repo), home)
    before = read_global_record(home).installed["audit"]

    _record, report = reconcile_global_record(home)

    assert report.changed is False
    assert read_global_record(home).installed["audit"] == before


def test_backfill_dry_run_writes_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    global_skill_dir("mystery", home).mkdir(parents=True)

    _record, report = reconcile_global_record(home, persist=False)

    assert report.unknown == ["mystery"]
    assert read_global_record(home).installed == {}
