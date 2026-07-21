"""Tests for the shared skill inventory and the `status` dashboard.

Phase 4 of `plans/2026-07-21-recommendation-model.md`. `status` replaces a
five-command jigsaw (`status` + `list` + `global list` + `doctor` +
`global doctor`) for the question "what do I actually have right now".
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer import install
from skillpod.installer.paths import global_skill_dir
from skillpod.manifest import load as load_manifest
from skillpod.skillset.inventory import SkillState, take_inventory


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _skill_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n", encoding="utf-8")
    return d


def _project(tmp_path: Path, *, skills: str, pool: Path | None = None) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(exist_ok=True)
    source = (
        textwrap.dedent(f"""
        sources:
          - name: pool
            type: local
            path: {pool}
        """)
        if pool
        else ""
    )
    (proj / "skillfile.yml").write_text(
        f"version: 1\nagents: [claude]\n{source}skills: [{skills}]\n", encoding="utf-8"
    )
    return proj


def _inventory(proj: Path, home: Path | None = None):  # type: ignore[no-untyped-def]
    return take_inventory(load_manifest(proj / "skillfile.yml"), proj, home=home)


# ---- the four states -------------------------------------------------------


def test_installed_skill_is_project(tmp_path: Path, isolated_home: Path) -> None:
    pool = tmp_path / "pool"
    _skill_dir(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)

    inv = _inventory(proj, isolated_home)

    assert [s.state for s in inv.skills] == [SkillState.PROJECT]
    assert inv.satisfied == 1
    assert inv.from_project == 1


def test_globally_provided_skill_is_not_missing(
    tmp_path: Path, isolated_home: Path
) -> None:
    """`prefer_global` means the project never installs it — that is success,
    not an absence."""
    _skill_dir(global_skill_dir("audit", isolated_home).parent, "audit")
    proj = _project(tmp_path, skills="audit")

    inv = _inventory(proj, isolated_home)

    assert [s.state for s in inv.skills] == [SkillState.GLOBAL]
    assert inv.satisfied == 1
    assert inv.missing == []


def test_uninstalled_skill_is_missing(tmp_path: Path, isolated_home: Path) -> None:
    proj = _project(tmp_path, skills="audit")

    inv = _inventory(proj, isolated_home)

    assert inv.missing == ["audit"]
    assert inv.satisfied == 0


def test_user_skill_counts_as_satisfied_once_installed(
    tmp_path: Path, isolated_home: Path
) -> None:
    proj = _project(tmp_path, skills="")
    _skill_dir(proj / ".skillpod" / "user_skills", "handmade")
    install(proj)

    inv = _inventory(proj, isolated_home)

    assert [s.state for s in inv.skills] == [SkillState.USER]
    assert inv.from_user == 1


def test_uninstalled_user_skill_is_missing_not_broken(
    tmp_path: Path, isolated_home: Path
) -> None:
    """Content dropped into user_skills that has never been installed is not
    *broken* — it is not set up yet, and `install` is the fix. Calling it
    broken would send the user to `doctor`, which has nothing to tell them.
    """
    proj = _project(tmp_path, skills="")
    _skill_dir(proj / ".skillpod" / "user_skills", "handmade")

    inv = _inventory(proj, isolated_home)

    assert inv.missing == ["handmade"]
    assert inv.broken == []


# ---- broken beats present --------------------------------------------------


def test_missing_fanout_makes_a_skill_broken(
    tmp_path: Path, isolated_home: Path
) -> None:
    """Materialised is not the same as usable: an agent that cannot reach the
    skill is not being served by it."""
    pool = tmp_path / "pool"
    _skill_dir(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)
    (proj / ".claude" / "skills" / "audit").unlink()

    inv = _inventory(proj, isolated_home)

    assert inv.broken == ["audit"]
    assert inv.satisfied == 0
    assert "claude" in (inv.skills[0].detail or "")


def test_record_without_a_directory_is_broken(
    tmp_path: Path, isolated_home: Path
) -> None:
    pool = tmp_path / "pool"
    _skill_dir(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)
    import shutil

    shutil.rmtree(proj / ".skillpod" / "skills" / "audit")

    inv = _inventory(proj, isolated_home)

    assert inv.broken == ["audit"]
    assert "directory is gone" in (inv.skills[0].detail or "")


# ---- the dashboard ---------------------------------------------------------


def test_status_summarises_every_state(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    pool = tmp_path / "pool"
    for name in ("here", "broken-one"):
        _skill_dir(pool, name)
    _skill_dir(global_skill_dir("from-global", isolated_home).parent, "from-global")
    proj = _project(tmp_path, skills="here, broken-one, from-global, nowhere", pool=pool)
    # `nowhere` cannot resolve, so install the rest and let it stay absent.
    (proj / "skillfile.yml").write_text(
        (proj / "skillfile.yml").read_text(encoding="utf-8").replace(", nowhere", ""),
        encoding="utf-8",
    )
    install(proj)
    (proj / ".claude" / "skills" / "broken-one").unlink()
    (proj / "skillfile.yml").write_text(
        (proj / "skillfile.yml").read_text(encoding="utf-8").replace(
            "from-global]", "from-global, nowhere]"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["status", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 0, result.stdout
    inv = json.loads(result.stdout)["inventory"]
    assert inv["recommended"] == 4
    assert inv["satisfied"] == 2  # here (project) + from-global
    assert inv["from_project"] == 1
    assert inv["from_global"] == 1
    assert inv["missing"] == ["nowhere"]
    assert inv["broken"] == ["broken-one"]


def test_status_points_at_the_command_that_fixes_each_problem(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """A count with no next step leaves the user stuck."""
    proj = _project(tmp_path, skills="nowhere")

    result = runner.invoke(app, ["status", "--manifest", str(proj / "skillfile.yml")])

    assert result.exit_code == 0
    assert "missing:" in result.stdout
    assert "skillpod install" in result.stdout


def test_list_and_status_agree_about_the_same_skill(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Both read one shared inventory; two commands contradicting each other
    about the same skill is the failure this prevents."""
    pool = tmp_path / "pool"
    _skill_dir(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)
    (proj / ".claude" / "skills" / "audit").unlink()

    listed = runner.invoke(
        app, ["list", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    status = runner.invoke(
        app, ["status", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    layer = json.loads(listed.stdout)["skills"][0]["layer"]
    assert layer == "broken"
    assert json.loads(status.stdout)["inventory"]["broken"] == ["audit"]
