"""Tests for `install.prefer_global` — global-aware deduplication.

Phase 3 of `plans/2026-07-21-recommendation-model.md`. The premise is that an
agent reading `<project>/.<agent>/skills/` also reads `~/.<agent>/skills/`;
where that is unverified, skipping the project install would make the skill
silently unavailable, so the optimisation must not fire.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer import install
from skillpod.installer.layering import Layering, layering_for, merges_layers
from skillpod.installer.paths import global_skill_dir, project_record_path
from skillpod.record import io as record_io


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _global_skill(home: Path, name: str) -> None:
    d = global_skill_dir(name, home)
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n", encoding="utf-8")


def _pool(tmp_path: Path, *names: str) -> Path:
    pool = tmp_path / "pool"
    for name in names:
        d = pool / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n", encoding="utf-8")
    return pool


def _project(tmp_path: Path, manifest: str) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(manifest, encoding="utf-8")
    return proj


def _manifest(pool: Path, *, agents: str, skills: str, prefer_global: str = "") -> str:
    return textwrap.dedent(f"""
        version: 1
        agents: [{agents}]
        install:
          mode: symlink
          {prefer_global}
        sources:
          - name: pool
            type: local
            path: {pool}
        skills: [{skills}]
    """)


# ---- the layering table ----------------------------------------------------


def test_only_measured_agents_are_treated_as_merging() -> None:
    """An unverified agent must not be assumed to merge.

    Getting this wrong drops a skill the project recommends, with no error to
    explain why — much worse than the redundant copy that caution costs.
    """
    assert layering_for("claude") is Layering.MERGES
    for unmeasured in ("codex", "gemini", "cursor", "opencode", "antigravity"):
        assert layering_for(unmeasured) is Layering.UNKNOWN
        assert not merges_layers(unmeasured)


# ---- the default: satisfied by global --------------------------------------


def test_globally_present_skill_is_not_installed_again(
    tmp_path: Path, isolated_home: Path
) -> None:
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit", "polish")
    proj = _project(tmp_path, _manifest(pool, agents="claude", skills="audit, polish"))

    report = install(proj)

    assert report.satisfied_by_global == ["audit"]
    assert [s.name for s in report.installed] == ["polish"]
    assert not (proj / ".skillpod" / "skills" / "audit").exists()
    assert not (proj / ".claude" / "skills" / "audit").exists()
    # The skill that is *not* global is installed as normal.
    assert (proj / ".skillpod" / "skills" / "polish").is_dir()


def test_satisfied_skill_stays_out_of_the_project_record(
    tmp_path: Path, isolated_home: Path
) -> None:
    """The record describes this project's installs; a global skill is not one."""
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit", "polish")
    proj = _project(tmp_path, _manifest(pool, agents="claude", skills="audit, polish"))

    install(proj)

    recorded = record_io.read(project_record_path(proj)).installed
    assert set(recorded) == {"polish"}


# ---- opting out ------------------------------------------------------------


def test_prefer_global_false_forces_a_project_copy(
    tmp_path: Path, isolated_home: Path
) -> None:
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit")
    proj = _project(
        tmp_path,
        _manifest(pool, agents="claude", skills="audit", prefer_global="prefer_global: false"),
    )

    report = install(proj)

    assert report.satisfied_by_global == []
    assert (proj / ".skillpod" / "skills" / "audit").is_dir()


def test_prefer_global_false_warns_that_the_copy_is_outranked(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Claude Code documents "personal overrides project".

    So the project copy is materialised and then ignored. Saying nothing would
    leave the user wondering why their pinned version has no effect.
    """
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit")
    proj = _project(
        tmp_path,
        _manifest(pool, agents="claude", skills="audit", prefer_global="prefer_global: false"),
    )

    result = runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])

    assert result.exit_code == 0, result.stdout
    assert "will not be the one in use" in result.stdout
    assert "audit" in result.stdout


# ---- the conservative gate -------------------------------------------------


def test_an_unmeasured_agent_blocks_the_optimisation(
    tmp_path: Path, isolated_home: Path
) -> None:
    """`codex` layering is unverified, so the project copy must still be made —
    otherwise codex would simply never see the skill."""
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit")
    proj = _project(tmp_path, _manifest(pool, agents="claude, codex", skills="audit"))

    report = install(proj)

    assert report.satisfied_by_global == []
    assert (proj / ".skillpod" / "skills" / "audit").is_dir()


def test_no_declared_agents_means_no_deduplication(
    tmp_path: Path, isolated_home: Path
) -> None:
    """With no agents there is no merging behaviour to rely on."""
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit")
    proj = _project(tmp_path, _manifest(pool, agents="", skills="audit"))

    report = install(proj)

    assert report.satisfied_by_global == []
    assert (proj / ".skillpod" / "skills" / "audit").is_dir()


# ---- what the user sees ----------------------------------------------------


def test_list_labels_the_layer_each_skill_comes_from(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit", "polish")
    proj = _project(tmp_path, _manifest(pool, agents="claude", skills="audit, polish"))
    install(proj)

    result = runner.invoke(
        app, ["list", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 0
    layers = {s["name"]: s["layer"] for s in json.loads(result.stdout)["skills"]}
    assert layers == {"audit": "global", "polish": "project"}


def test_doctor_treats_a_globally_satisfied_skill_as_fine(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """It is not "missing" — it is provided by the other layer."""
    _global_skill(isolated_home, "audit")
    pool = _pool(tmp_path, "audit")
    proj = _project(tmp_path, _manifest(pool, agents="claude", skills="audit"))
    install(proj)

    result = runner.invoke(
        app, ["doctor", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 0
    codes = {f["code"] for f in json.loads(result.stdout)["findings"]}
    assert "satisfied-by-global" in codes
    assert "not-installed" not in codes
