"""Tests for project profiles actually reconciling fan-out.

Phase 6 of `plans/2026-07-21-recommendation-model.md` — the last of the three
defects Phase 0 pinned. A project-scope `switch` used to write only a pointer:
`resolve` and `status` honoured the profile while the agent went on loading
everything, so the setting *looked* like it worked.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer import install
from skillpod.installer.paths import agent_skill_dir, project_skill_dir


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _pool(tmp_path: Path, *names: str) -> Path:
    pool = tmp_path / "pool"
    for name in names:
        d = pool / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n", encoding="utf-8")
    return pool


def _project(tmp_path: Path, pool: Path, *, profiles: str = "") -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            install:
              prefer_global: false
            sources:
              - name: pool
                type: local
                path: {pool}
            skills: [audit, polish]
        """).lstrip()
        + profiles,
        encoding="utf-8",
    )
    return proj


_MINIMAL = "profiles:\n  minimal:\n    skills: [audit]\n"


def _invoke(runner: CliRunner, proj: Path, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, [*args, "--manifest", str(proj / "skillfile.yml")])


# ---- switching changes what the agent sees ---------------------------------


def test_switch_hides_excluded_skills_but_keeps_them_installed(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Hiding must not mean deleting — switching back has to be instant and
    offline, which is the whole reason profiles filter fan-out rather than
    the materialised set."""
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)

    result = _invoke(runner, proj, "switch", "minimal")

    assert result.exit_code == 0, result.stdout
    assert agent_skill_dir(proj, "claude", "audit").exists()
    assert not agent_skill_dir(proj, "claude", "polish").exists()
    # Still on disk, so switching back needs no download.
    assert project_skill_dir(proj, "polish").is_dir()


def test_switching_back_restores_the_hidden_skill(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    proj = _project(
        tmp_path,
        _pool(tmp_path, "audit", "polish"),
        profiles="profiles:\n  minimal:\n    skills: [audit]\n  full:\n    skills: [audit, polish]\n",
    )
    install(proj)
    _invoke(runner, proj, "switch", "minimal")

    result = _invoke(runner, proj, "switch", "full")

    assert result.exit_code == 0, result.stdout
    assert agent_skill_dir(proj, "claude", "polish").exists()


def test_switch_reports_what_it_hid(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)

    result = _invoke(runner, proj, "switch", "minimal", "--json")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["unlinked"] == ["polish"]


def test_dry_run_changes_nothing(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)

    result = _invoke(runner, proj, "switch", "minimal", "--dry-run", "--json")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["unlinked"] == ["polish"]
    assert agent_skill_dir(proj, "claude", "polish").exists()


# ---- the other commands must not undo it -----------------------------------


def test_sync_does_not_resurrect_a_hidden_skill(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """`sync` rebuilds fan-out from the record. Rebuilding *everything* would
    silently undo the switch the user just made."""
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)
    _invoke(runner, proj, "switch", "minimal")

    result = _invoke(runner, proj, "sync", "--json")

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["hidden"] == ["polish"]
    assert not agent_skill_dir(proj, "claude", "polish").exists()


def test_install_does_not_resurrect_a_hidden_skill(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)
    _invoke(runner, proj, "switch", "minimal")

    report = install(proj)

    assert report.hidden_by_profile == ["polish"]
    assert not agent_skill_dir(proj, "claude", "polish").exists()
    # Materialised regardless — hidden is not uninstalled.
    assert project_skill_dir(proj, "polish").is_dir()


# ---- refusals --------------------------------------------------------------


def test_switching_to_an_unknown_profile_is_rejected(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Writing the pointer without checking left projects where every later
    `resolve` failed, with nothing pointing at the cause."""
    proj = _project(tmp_path, _pool(tmp_path, "audit", "polish"), profiles=_MINIMAL)
    install(proj)

    result = _invoke(runner, proj, "switch", "nonexistent")

    assert result.exit_code == 1
    assert "nonexistent" in result.stdout + (result.stderr or "")
    # And the previous state is untouched.
    assert agent_skill_dir(proj, "claude", "polish").exists()


def test_switch_outside_a_project_points_at_the_global_scope(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    result = runner.invoke(
        app,
        ["switch", "dev", "--scope", "project", "--manifest", str(tmp_path / "absent.yml")],
    )

    assert result.exit_code == 1
    assert "--scope global" in result.stdout + (result.stderr or "")
