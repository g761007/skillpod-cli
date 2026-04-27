"""Tests for the installer capability.

Scenarios trace to
`openspec/changes/add-skillpod-mvp-install/specs/installer/spec.md` and
`specs/lockfile/spec.md`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import httpx
import pytest
import respx

from skillpod import lockfile as lockfile_pkg
from skillpod.installer import (
    InstallConflict,
    InstallSystemError,
    InstallUserError,
    install,
    uninstall,
)
from skillpod.lockfile.integrity import hash_directory
from tests._git_fixtures import make_skill_repo

_REGISTRY_BASE = "https://registry.test"


@pytest.fixture(autouse=True)
def isolated_cache_and_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    monkeypatch.setenv("SKILLPOD_REGISTRY_URL", _REGISTRY_BASE)


def _project(tmp_path: Path, manifest: str) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(manifest, encoding="utf-8")
    return proj


# ---- Local-only end-to-end --------------------------------------------------


def test_local_skill_materialised_and_fanned_out(tmp_path: Path) -> None:
    """Scenario: Three-agent fan-out (local source variant) +
    Materialisation under .skillpod/skills."""
    skills_root = tmp_path / "agents-pool"
    (skills_root / "audit").mkdir(parents=True)
    (skills_root / "audit" / "manifest.md").write_text("# audit", encoding="utf-8")

    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude, codex, gemini]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills:
              - audit
        """),
    )

    report = install(proj)

    assert [s.name for s in report.installed] == ["audit"]
    skill_link = proj / ".skillpod" / "skills" / "audit"
    assert skill_link.is_symlink()
    assert (skill_link / "manifest.md").is_file()

    for agent in ("claude", "codex", "gemini"):
        link = proj / f".{agent}" / "skills" / "audit"
        assert link.is_symlink()
        # All agents resolve through .skillpod/skills/audit -> the skill dir.
        assert link.resolve() == skill_link.resolve()


def test_local_skill_does_not_get_lockfile_entry(tmp_path: Path) -> None:
    """Scenario: Manifest with a local skill produces no lock entry."""
    skills_root = tmp_path / "pool"
    (skills_root / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit]
        """),
    )

    install(proj)

    lock = lockfile_pkg.read(proj / "skillfile.lock")
    assert lock.resolved == {}


def test_agents_not_listed_get_no_fanout(tmp_path: Path) -> None:
    """Scenario: Restricting fan-out to two agents."""
    skills_root = tmp_path / "pool"
    (skills_root / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude, codex]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit]
        """),
    )
    install(proj)
    assert (proj / ".claude" / "skills" / "audit").is_symlink()
    assert (proj / ".codex" / "skills" / "audit").is_symlink()
    for absent in ("gemini", "cursor", "opencode", "antigravity"):
        assert not (proj / f".{absent}" / "skills").exists()


# ---- Git source: lockfile written, no registry leakage ---------------------


def test_git_skill_writes_lockfile_with_no_registry_field(tmp_path: Path) -> None:
    """Scenario: Lockfile after first install + Registry name absent."""
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: anthropic
                type: git
                url: {repo_path}
                ref: main
            skills:
              - name: audit
                source: anthropic
        """),
    )

    report = install(proj)

    [installed] = report.installed
    assert installed.resolved.commit == sha
    assert installed.sha256 == hash_directory(installed.project_path)

    lock = lockfile_pkg.read(proj / "skillfile.lock")
    assert "audit" in lock.resolved
    locked = lock.resolved["audit"]
    assert locked.source == "git"
    assert locked.url == str(repo_path)
    assert locked.commit == sha
    assert len(locked.sha256) == 64
    text = (proj / "skillfile.lock").read_text(encoding="utf-8")
    assert "registry" not in text


# ---- Frozen mode (lockfile drift) ------------------------------------------


def test_frozen_mode_commit_drift_aborts(tmp_path: Path) -> None:
    """Scenario: Lockfile commit drift aborts install."""
    repo_path, _real_sha = make_skill_repo(tmp_path / "git-side")
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: anthropic
                type: git
                url: {repo_path}
                ref: main
            skills:
              - name: audit
                source: anthropic
        """),
    )

    bad_commit = "deadbeef" * 5  # 40 hex chars, never matches the real commit
    fake_sha = "f" * 64
    (proj / "skillfile.lock").write_text(
        textwrap.dedent(f"""
            version: 1
            resolved:
              audit:
                source: git
                url: {repo_path}
                commit: {bad_commit}
                sha256: {fake_sha}
        """).lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(InstallSystemError):
        # Resolving the locked (nonexistent) commit fails inside git checkout.
        install(proj)

    # Project unchanged
    assert not (proj / ".skillpod").exists()
    assert not (proj / ".claude").exists()


def test_frozen_mode_round_trip_succeeds(tmp_path: Path) -> None:
    """Re-running install after a successful run uses the lockfile and
    leaves it unchanged."""
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: anthropic
                type: git
                url: {repo_path}
                ref: main
            skills:
              - name: audit
                source: anthropic
        """),
    )
    install(proj)
    first_lock = (proj / "skillfile.lock").read_text(encoding="utf-8")

    second = install(proj)
    second_lock = (proj / "skillfile.lock").read_text(encoding="utf-8")

    assert second.installed[0].resolved.commit == sha
    assert first_lock == second_lock


# ---- Registry fallback ------------------------------------------------------


@respx.mock
def test_registry_fallback_when_no_source_matches(tmp_path: Path) -> None:
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "audit",
                "repo": {
                    "host": "github.com",
                    "org": "vercel-labs",
                    "name": "agent-skills",
                    "url": str(repo_path),
                },
                "ref": "main",
                "commit": sha,
                "meta": {"verified": True, "installs": 0, "stars": 0},
            },
        )
    )

    proj = _project(
        tmp_path,
        textwrap.dedent("""
            version: 1
            agents: [claude]
            skills: [audit]
        """),
    )

    install(proj)
    lock = lockfile_pkg.read(proj / "skillfile.lock")
    locked = lock.resolved["audit"]
    assert locked.commit == sha
    assert locked.url == str(repo_path)


@respx.mock
def test_registry_failure_aborts_and_leaves_no_artefacts(tmp_path: Path) -> None:
    """Scenario: Registry timeout aborts install."""
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        side_effect=httpx.ConnectTimeout("nope")
    )
    proj = _project(
        tmp_path,
        textwrap.dedent("""
            version: 1
            agents: [claude]
            skills: [audit]
        """),
    )
    with pytest.raises(InstallSystemError):
        install(proj)
    assert not (proj / ".skillpod").exists()
    assert not (proj / ".claude").exists()
    assert not (proj / "skillfile.lock").exists()


# ---- Conflict refusal -------------------------------------------------------


def test_refuses_to_overwrite_unmanaged_directory(tmp_path: Path) -> None:
    """Scenario: Hand-managed skill is preserved."""
    skills_root = tmp_path / "pool"
    (skills_root / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit]
        """),
    )
    # Pre-existing user content at the fan-out target.
    user_dir = proj / ".claude" / "skills" / "audit"
    user_dir.mkdir(parents=True)
    (user_dir / "user-content.md").write_text("hands off", encoding="utf-8")

    with pytest.raises(InstallConflict):
        install(proj)

    # User content untouched + nothing materialised + no lockfile.
    assert (user_dir / "user-content.md").read_text() == "hands off"
    assert not (proj / "skillfile.lock").exists()
    # Rollback removed the .skillpod/skills/audit symlink it had created.
    assert not (proj / ".skillpod" / "skills" / "audit").exists()


def test_unresolvable_skill_aborts(tmp_path: Path) -> None:
    """Scenario: Unresolvable skill aborts install (default on_missing=error)."""
    skills_root = tmp_path / "pool"
    skills_root.mkdir()
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills:
              - name: ghost
                source: local
        """),
    )
    with pytest.raises(InstallUserError):
        install(proj)
    assert not (proj / ".skillpod").exists()


# ---- uninstall --------------------------------------------------------------


def test_uninstall_removes_links_only_for_target_skill(tmp_path: Path) -> None:
    skills_root = tmp_path / "pool"
    for name in ("audit", "polish"):
        (skills_root / name).mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude, codex]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit, polish]
        """),
    )
    install(proj)
    assert (proj / ".skillpod" / "skills" / "audit").is_symlink()
    assert (proj / ".skillpod" / "skills" / "polish").is_symlink()

    uninstall(proj, "audit")

    assert not (proj / ".skillpod" / "skills" / "audit").exists()
    assert (proj / ".skillpod" / "skills" / "polish").is_symlink()
    for agent in ("claude", "codex"):
        assert not (proj / f".{agent}" / "skills" / "audit").exists()
        assert (proj / f".{agent}" / "skills" / "polish").is_symlink()


# ---- Idempotency ------------------------------------------------------------


def test_repeated_install_is_idempotent(tmp_path: Path) -> None:
    skills_root = tmp_path / "pool"
    (skills_root / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit]
        """),
    )
    install(proj)
    snapshot = sorted(p.relative_to(proj).as_posix() for p in proj.rglob("*"))
    install(proj)
    snapshot2 = sorted(p.relative_to(proj).as_posix() for p in proj.rglob("*"))
    assert snapshot == snapshot2


# ---- Trust enforcement (Phase B) -------------------------------------------


@respx.mock
def test_trust_error_on_unverified_skill_is_user_error_code_1(tmp_path: Path) -> None:
    """Registry returns verified=false, default policy -> InstallUserError (exit 1)."""
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "audit",
                "repo": {
                    "host": "github.com",
                    "org": "vercel-labs",
                    "name": "agent-skills",
                    "url": str(repo_path),
                },
                "ref": "main",
                "commit": sha,
                "meta": {"verified": False, "installs": 0, "stars": 0},
            },
        )
    )

    proj = _project(
        tmp_path,
        textwrap.dedent("""
            version: 1
            agents: [claude]
            skills: [audit]
        """),
    )

    with pytest.raises(InstallUserError, match="not verified"):
        install(proj)

    # Project unchanged.
    assert not (proj / ".skillpod").exists()
    assert not (proj / ".claude").exists()
