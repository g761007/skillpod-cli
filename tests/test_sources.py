"""Tests for the source-resolver capability.

Scenarios trace to
`openspec/changes/add-skillpod-mvp-install/specs/source-resolver/spec.md`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from skillpod.manifest.models import SkillEntry, SourceEntry
from skillpod.sources import (
    GitOperationError,
    ResolvedSkill,
    SourceError,
    SourceNotFound,
    cache_path_for,
    cache_root,
    parse_repo_url,
    populate_cache,
    resolve_default_branch,
    resolve_from_sources,
    resolve_git,
    resolve_local,
    resolve_ref,
)
from tests._git_fixtures import make_root_skill_repo, make_skill_repo


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point SKILLPOD_CACHE_DIR at a fresh tmpdir for every test."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    return cache


# ---- cache layout & URL parsing --------------------------------------------


def test_cache_root_honours_env(isolated_cache: Path) -> None:
    assert cache_root() == isolated_cache


@pytest.mark.parametrize(
    ("url", "expected_host", "expected_path"),
    [
        ("https://github.com/example/skills", "github.com", "example/skills"),
        ("https://github.com/example/skills.git", "github.com", "example/skills"),
        ("git@github.com:example/skills.git", "github.com", "example/skills"),
        ("ssh://git@github.com/example/skills.git", "github.com", "example/skills"),
        ("file:///tmp/skills.git", "", "tmp/skills"),
    ],
)
def test_parse_repo_url(url: str, expected_host: str, expected_path: str) -> None:
    host, path = parse_repo_url(url)
    if expected_host:
        assert host == expected_host
    assert path == expected_path


def test_cache_path_layout(isolated_cache: Path) -> None:
    sha = "a" * 40
    p = cache_path_for("https://github.com/example/skills", sha)
    assert p == isolated_cache / "github.com" / f"example/skills@{sha}"


def test_cache_path_rejects_short_sha() -> None:
    with pytest.raises(ValueError, match="40-character"):
        cache_path_for("https://github.com/example/skills", "abc")


# ---- local source -----------------------------------------------------------


def test_resolve_local_hit(tmp_path: Path) -> None:
    """Scenario: Local source hit."""
    root = tmp_path / "agents"
    (root / "audit").mkdir(parents=True)
    src = SourceEntry(name="local", type="local", path=str(root))
    resolved = resolve_local("audit", src)
    assert resolved.source_kind == "local"
    assert resolved.path == (root / "audit").resolve()
    assert resolved.commit is None
    assert resolved.url is None


def test_resolve_local_missing(tmp_path: Path) -> None:
    src = SourceEntry(name="local", type="local", path=str(tmp_path))
    with pytest.raises(SourceNotFound):
        resolve_local("ghost", src)


def test_resolve_local_path_is_file(tmp_path: Path) -> None:
    (tmp_path / "audit").write_text("not a dir", encoding="utf-8")
    src = SourceEntry(name="local", type="local", path=str(tmp_path))
    with pytest.raises(SourceError, match="not a directory"):
        resolve_local("audit", src)


# ---- git source -------------------------------------------------------------


def test_resolve_git_populates_cache(tmp_path: Path, isolated_cache: Path) -> None:
    """Scenario: Git resolve populates cache."""
    repo_path, sha = make_skill_repo(tmp_path)
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")

    resolved = resolve_git("audit", src)

    assert resolved.commit == sha
    assert resolved.url == str(repo_path)
    expected_cache = cache_path_for(str(repo_path), sha)
    assert expected_cache.is_dir()
    assert resolved.path == (expected_cache / "audit").resolve()
    # Real working tree, with the committed file.
    assert (resolved.path / "manifest.md").is_file()


def test_resolve_git_explicit_commit(tmp_path: Path) -> None:
    repo_path, sha = make_skill_repo(tmp_path)
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")
    skill = SkillEntry(name="audit", source="anthropic", version=sha)

    resolved = resolve_from_sources(skill, [src])

    assert resolved.commit == sha


def test_re_resolving_does_not_reclone(
    tmp_path: Path, isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario: Re-running install reuses cache."""
    repo_path, sha = make_skill_repo(tmp_path)
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")

    resolve_git("audit", src)  # warm the cache

    # Sentinel file inside the cache: if a re-resolve reclones, the rename
    # would replace the directory and lose the sentinel.
    cache_dir = cache_path_for(str(repo_path), sha)
    sentinel = cache_dir / ".cache-sentinel"
    sentinel.write_text("kept", encoding="utf-8")

    resolved = resolve_git("audit", src)

    assert sentinel.is_file()
    assert resolved.path == (cache_dir / "audit").resolve()


def test_populate_cache_idempotent(tmp_path: Path) -> None:
    repo_path, sha = make_skill_repo(tmp_path)
    a = populate_cache(str(repo_path), sha)
    b = populate_cache(str(repo_path), sha)
    assert a == b
    assert a.is_dir()


def test_resolve_ref_returns_sha_when_already_sha(tmp_path: Path) -> None:
    repo_path, sha = make_skill_repo(tmp_path)
    assert resolve_ref(str(repo_path), sha) == sha


def test_resolve_ref_unknown(tmp_path: Path) -> None:
    repo_path, _ = make_skill_repo(tmp_path)
    with pytest.raises(GitOperationError):
        resolve_ref(str(repo_path), "no-such-branch")


def test_resolve_default_branch_main(tmp_path: Path) -> None:
    """A repo whose default branch is `main` returns "main"."""
    repo_path, _ = make_skill_repo(tmp_path, branch="main")
    assert resolve_default_branch(str(repo_path)) == "main"


def test_resolve_default_branch_master(tmp_path: Path) -> None:
    """A repo whose default branch is `master` returns "master" — this is
    the regression that broke `skillpod add owner/repo` for repositories
    that never migrated off the historical default."""
    repo_path, _ = make_skill_repo(tmp_path, branch="master")
    assert resolve_default_branch(str(repo_path)) == "master"


def test_resolve_default_branch_custom(tmp_path: Path) -> None:
    """An arbitrary default-branch name is parsed correctly."""
    repo_path, _ = make_skill_repo(tmp_path, branch="develop")
    assert resolve_default_branch(str(repo_path)) == "develop"


def test_git_skill_missing_in_repo(tmp_path: Path) -> None:
    repo_path, _ = make_skill_repo(tmp_path)
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")
    with pytest.raises(SourceError, match="not present"):
        resolve_git("does-not-exist", src)


def test_resolve_git_falls_back_to_root_when_repo_is_skill(tmp_path: Path) -> None:
    """A repo whose root *is* the skill (top-level SKILL.md) resolves to
    `repo_root` itself rather than failing on the missing subdir."""
    repo_path, sha = make_root_skill_repo(tmp_path, repo_name="vibe")
    src = SourceEntry(name="vibe", type="git", url=str(repo_path), ref="main")

    resolved = resolve_git("vibe", src)

    expected_cache = cache_path_for(str(repo_path), sha)
    assert resolved.path == expected_cache.resolve()
    assert (resolved.path / "SKILL.md").is_file()
    assert resolved.commit == sha


def test_resolve_git_root_fallback_works_for_any_skill_name(tmp_path: Path) -> None:
    """When the repo root has SKILL.md, the fallback uses the root regardless
    of the requested `skill_name` — manifests can store any logical name."""
    repo_path, _sha = make_root_skill_repo(tmp_path, repo_name="single")
    src = SourceEntry(name="single", type="git", url=str(repo_path), ref="main")

    resolved = resolve_git("renamed-locally", src)

    assert (resolved.path / "SKILL.md").is_file()


def test_resolve_git_no_fallback_when_no_skill_md_anywhere(tmp_path: Path) -> None:
    """If neither `<repo>/<name>/` nor `<repo>/SKILL.md` exists, still fail."""
    repo_path, _sha = make_skill_repo(tmp_path, skill_name="audit")
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")

    with pytest.raises(SourceError, match="not present"):
        resolve_git("ghost", src)


# ---- priority & explicit source --------------------------------------------


def test_higher_priority_wins(tmp_path: Path) -> None:
    """Scenario: Higher priority wins."""
    local_root = tmp_path / "local-skills"
    (local_root / "audit").mkdir(parents=True)
    repo_path, _ = make_skill_repo(tmp_path / "git-side")

    sources = [
        SourceEntry(name="anthropic", type="git", url=str(repo_path), priority=80),
        SourceEntry(name="local", type="local", path=str(local_root), priority=100),
    ]
    skill = SkillEntry(name="audit")

    resolved = resolve_from_sources(skill, sources)

    assert resolved.source_kind == "local"
    assert resolved.source_name == "local"
    assert resolved.commit is None  # git source was not consulted


def test_explicit_source_forces_git(tmp_path: Path) -> None:
    """Scenario: Explicit source forces git resolution."""
    local_root = tmp_path / "local-skills"
    (local_root / "audit").mkdir(parents=True)
    repo_path, sha = make_skill_repo(tmp_path / "git-side")

    sources = [
        SourceEntry(name="anthropic", type="git", url=str(repo_path), priority=80),
        SourceEntry(name="local", type="local", path=str(local_root), priority=100),
    ]
    skill = SkillEntry(name="audit", source="anthropic")

    resolved = resolve_from_sources(skill, sources)

    assert resolved.source_kind == "git"
    assert resolved.commit == sha


def test_explicit_source_must_be_declared(tmp_path: Path) -> None:
    skill = SkillEntry(name="audit", source="missing")
    with pytest.raises(SourceError, match="not declared"):
        resolve_from_sources(skill, [])


def test_no_source_satisfies_skill(tmp_path: Path) -> None:
    src = SourceEntry(name="local", type="local", path=str(tmp_path))
    skill = SkillEntry(name="audit")
    with pytest.raises(SourceNotFound, match="no declared source"):
        resolve_from_sources(skill, [src])


# ---- ResolvedSkill is hashable / immutable ---------------------------------


def test_resolved_skill_is_frozen(tmp_path: Path) -> None:
    rs = ResolvedSkill(
        name="audit",
        source_kind="local",
        source_name="local",
        path=tmp_path,
        url=None,
        commit=None,
    )
    with pytest.raises(Exception):
        rs.name = "other"  # type: ignore[misc]


# ---- Cleanup of staging dirs -----------------------------------------------


def test_failed_clone_does_not_leave_partial_cache(
    tmp_path: Path, isolated_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failures during git operations must not leave a partial entry in the cache."""
    repo_path, _sha = make_skill_repo(tmp_path)

    # Corrupt the repo so `git clone` succeeds but `git checkout` fails on
    # an unknown commit.
    src = SourceEntry(name="anthropic", type="git", url=str(repo_path), ref="main")
    bad_commit = "0" * 40
    skill = SkillEntry(name="audit", source="anthropic", version=bad_commit)

    with pytest.raises(GitOperationError):
        resolve_from_sources(skill, [src])

    bad_path = cache_path_for(str(repo_path), bad_commit)
    assert not bad_path.exists()


# ---- helper for nested cleanup ---------------------------------------------


@pytest.fixture(autouse=True)
def _scrub_tmp_workdirs() -> None:
    """No-op fixture kept as an extension point if cleanup ever grows."""
    yield


del shutil  # silence "imported but unused" — kept available for future tests
