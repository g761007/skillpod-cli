"""Tests for `skillpod link` / `skillpod unlink`.

Phase 5 of `plans/2026-07-21-recommendation-model.md`. One verb pair for both
scopes: the project side previously had to be expressed as `add`/`remove`,
which also downloads and edits the manifest — far more than "should this agent
see this skill".
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer import install
from skillpod.installer.paths import agent_skill_dir, global_skill_dir


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _skill(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n", encoding="utf-8")
    return d


def _project(tmp_path: Path, *, skills: str = "", pool: Path | None = None) -> Path:
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
        f"version: 1\nagents: [claude]\ninstall:\n  prefer_global: false\n"
        f"{source}skills: [{skills}]\n",
        encoding="utf-8",
    )
    return proj


def _invoke(runner: CliRunner, proj: Path, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, [*args, "--manifest", str(proj / "skillfile.yml")])


# ---- the round trip --------------------------------------------------------


def test_unlink_keeps_the_copy_so_relinking_needs_no_download(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """That is the whole point of a separate verb: `remove` would delete the
    content and edit the manifest, which is not what "turn this off" means."""
    pool = tmp_path / "pool"
    _skill(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)

    unlinked = _invoke(runner, proj, "unlink", "audit")

    assert unlinked.exit_code == 0, unlinked.stdout
    assert not agent_skill_dir(proj, "claude", "audit").exists()
    assert (proj / ".skillpod" / "skills" / "audit").is_dir()
    # Still recommended by the manifest — unlinking is not removing.
    assert "audit" in (proj / "skillfile.yml").read_text(encoding="utf-8")

    relinked = _invoke(runner, proj, "link", "audit")

    assert relinked.exit_code == 0, relinked.stdout
    assert agent_skill_dir(proj, "claude", "audit").exists()


def test_link_pulls_from_the_global_copy_instead_of_fetching(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """A skill already on the machine should never be downloaded again."""
    _skill(global_skill_dir("xlsx", isolated_home).parent, "xlsx")
    proj = _project(tmp_path)

    result = _invoke(runner, proj, "link", "xlsx", "--json")

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["copied_from_global"] is True
    assert payload["linked"] == ["claude"]
    assert (proj / ".skillpod" / "skills" / "xlsx").is_dir()


# ---- refusals --------------------------------------------------------------


def test_linking_something_nowhere_on_the_machine_says_what_to_run(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """`link` cannot invent content, and the error has to name the command
    that can."""
    proj = _project(tmp_path)

    result = _invoke(runner, proj, "link", "nowhere")

    assert result.exit_code == 1
    combined = result.stdout + (result.stderr or "")
    assert "not installed in this project or globally" in combined
    assert "skillpod add" in combined


def test_undeclared_agent_is_rejected_with_the_declared_list(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    _skill(global_skill_dir("xlsx", isolated_home).parent, "xlsx")
    proj = _project(tmp_path)

    result = _invoke(runner, proj, "link", "xlsx", "-a", "codex")

    assert result.exit_code == 1
    combined = result.stdout + (result.stderr or "")
    assert "codex" in combined
    assert "declared: claude" in combined


def test_unlink_leaves_entries_skillpod_did_not_create(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Deleting a directory the user put there by hand would be destroying
    work skillpod does not own."""
    pool = tmp_path / "pool"
    _skill(pool, "audit")
    proj = _project(tmp_path, skills="audit", pool=pool)
    install(proj)
    link = agent_skill_dir(proj, "claude", "audit")
    link.unlink()
    link.mkdir(parents=True)
    (link / "mine.md").write_text("hand-made", encoding="utf-8")

    result = _invoke(runner, proj, "unlink", "audit", "--json")

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["skipped_unmanaged"] == ["claude"]
    assert (link / "mine.md").read_text(encoding="utf-8") == "hand-made"


# ---- scope selection -------------------------------------------------------


def test_g_flag_targets_the_global_skill_set(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    _skill(global_skill_dir("xlsx", isolated_home).parent, "xlsx")
    proj = _project(tmp_path)

    linked = _invoke(runner, proj, "link", "xlsx", "-g", "-a", "claude", "-y")

    assert linked.exit_code == 0, linked.stdout
    assert (isolated_home / ".claude" / "skills" / "xlsx").exists()
    # The project was left alone.
    assert not (proj / ".skillpod" / "skills" / "xlsx").exists()


def test_link_without_a_manifest_points_at_the_global_flag(
    runner: CliRunner, tmp_path: Path, isolated_home: Path
) -> None:
    """Outside a project the useful advice is `-g`, not "run init"."""
    result = runner.invoke(
        app, ["link", "xlsx", "--manifest", str(tmp_path / "absent.yml")]
    )

    assert result.exit_code == 1
    assert "-g" in result.stdout + (result.stderr or "")
