"""Acceptance tests for the recommendation model.

Traces to `plans/2026-07-21-recommendation-model.md`, Phase 0 ("pin current
behaviour"). Each test states behaviour skillpod is *supposed* to have once the
plan lands; all three fail today.

They are marked ``xfail(strict=True)`` deliberately:

- CI stays green while the defects are pinned, so this branch is mergeable.
- ``strict`` turns an *unexpected pass* into a build failure, so the moment a
  later phase fixes one, the marker must be removed rather than silently
  rotting into a test that no longer asserts anything.

Remove the marker in the phase that fixes each defect:
  Phase 6 → project profiles, Phase 3 → global dedup, Phase 1 → provenance.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer.global_apply import execute_apply, plan_apply
from skillpod.installer.paths import global_skill_dir
from skillpod.profile.models import GlobalProfileBody
from skillpod.profile.snapshot import recover_source
from tests._git_fixtures import make_root_skill_repo


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point HOME and the git cache at tmp_path so the user's real global
    skill set is never read or mutated by these tests.

    ``USERPROFILE`` is set alongside ``HOME`` because ``Path.home()`` resolves
    via ``ntpath.expanduser`` on Windows, which consults ``USERPROFILE`` and
    ignores ``HOME`` entirely — setting only ``HOME`` would leave these tests
    reading and writing the developer's real home directory there.
    """
    home = tmp_path / "home"
    home.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    monkeypatch.delenv("SKILLPOD_ACTIVE_PROFILE", raising=False)
    return home


def _skill_pool(tmp_path: Path, *names: str) -> Path:
    """A local source directory holding one trivial skill per name."""
    pool = tmp_path / "pool"
    for name in names:
        skill = pool / name
        skill.mkdir(parents=True)
        skill.joinpath("SKILL.md").write_text(
            f"---\ndescription: {name}\n---\n# {name}\n", encoding="utf-8"
        )
    return pool


def _project(tmp_path: Path, manifest: str) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(manifest, encoding="utf-8")
    return proj


# ---------------------------------------------------------------------------
# Need #1 — a project profile must actually change what the agent sees
# ---------------------------------------------------------------------------


def test_project_profile_switch_unlinks_excluded_skills(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Switching to a profile that omits a skill must remove its fan-out.

    A profile the agent cannot observe is decorative: the whole point of
    `switch minimal` is that the agent stops loading `polish`.

    Fixed in Phase 6. `switch` reconciles fan-out through
    `installer/project_apply.py`, and `sync` honours the active profile rather
    than rebuilding every link and silently undoing the switch.
    """
    pool = _skill_pool(tmp_path, "audit", "polish")
    manifest_path = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: pool
                type: local
                path: {pool}
            skills:
              - audit
              - polish
            profiles:
              minimal:
                skills: [audit]
        """),
    ) / "skillfile.yml"
    proj = manifest_path.parent

    installed = runner.invoke(app, ["install", "--manifest", str(manifest_path)])
    assert installed.exit_code == 0, installed.stdout
    assert (proj / ".claude" / "skills" / "audit").exists()
    assert (proj / ".claude" / "skills" / "polish").exists()

    switched = runner.invoke(app, ["switch", "minimal", "--manifest", str(manifest_path)])
    assert switched.exit_code == 0, switched.stdout

    # The read path already honours the profile — this much works today.
    resolved = runner.invoke(
        app, ["resolve", "--json", "--manifest", str(manifest_path)]
    )
    assert resolved.exit_code == 0, resolved.stdout
    assert "polish" not in resolved.stdout

    synced = runner.invoke(app, ["sync", "--manifest", str(manifest_path)])
    assert synced.exit_code == 0, synced.stdout

    # ...but the filesystem the agent actually reads is unchanged.
    assert (proj / ".claude" / "skills" / "audit").exists()
    assert not (proj / ".claude" / "skills" / "polish").exists()


# ---------------------------------------------------------------------------
# Need #2 — a skill already installed globally must not be duplicated
# ---------------------------------------------------------------------------


def test_project_install_skips_skill_already_present_globally(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """A recommendation already satisfied globally needs no project copy.

    Fixed in Phase 3 by `install.prefer_global`, which defaults to true: if you
    already have the skill, the recommendation is met. It applies only where
    every declared agent is known to merge its personal and project skill
    directories — see `skillpod.installer.layering`.
    """
    global_audit = global_skill_dir("audit", isolated_home)
    global_audit.mkdir(parents=True)
    global_audit.joinpath("SKILL.md").write_text(
        "---\ndescription: audit\n---\n# audit\n", encoding="utf-8"
    )

    pool = _skill_pool(tmp_path, "audit", "polish")
    manifest_path = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: pool
                type: local
                path: {pool}
            skills:
              - audit
              - polish
        """),
    ) / "skillfile.yml"
    proj = manifest_path.parent

    installed = runner.invoke(app, ["install", "--manifest", str(manifest_path)])
    assert installed.exit_code == 0, installed.stdout

    # 'polish' is not global, so the project still owns it.
    assert (proj / ".skillpod" / "skills" / "polish").is_dir()
    # 'audit' is already satisfied by the global layer.
    assert not (proj / ".skillpod" / "skills" / "audit").exists()


# ---------------------------------------------------------------------------
# Need #3 — a global install must record where it came from
# ---------------------------------------------------------------------------


def test_global_install_keeps_source_recoverable(tmp_path: Path, isolated_home: Path) -> None:
    """Without provenance there is nothing for `global update` to update.

    Fixed in Phase 1c: `install_global` writes `~/.skillpod/installed.yml`, and
    `recover_source` consults it before falling back to symlink archaeology.
    This is also what makes `profile save` emit portable profiles again.
    """
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    body = GlobalProfileBody.model_validate(
        # as_uri() so the URL is valid on Windows too (file:///C:/...).
        {"skills": [{"name": "audit", "source": repo.as_uri()}]}
    )
    plan = plan_apply(body, agents=["claude"], home=isolated_home)
    report = execute_apply(body, plan, force=True, home=isolated_home)
    assert report.downloaded == ["audit"]

    recovered = recover_source("audit", isolated_home)
    assert recovered.name == "audit"
    assert recovered.source is not None, (
        "a git-sourced global skill must remember its origin so it can be updated"
    )
