"""Tests for global profile apply: source-bearing models + reconcile engine."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from skillpod.cli.commands import switch
from skillpod.installer.global_apply import execute_apply, plan_apply
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_skill_dir,
    is_managed_global_fanout,
)
from skillpod.profile.io import load_global_profile_body
from skillpod.profile.models import GlobalProfileBody, GlobalProfileFile
from tests._git_fixtures import make_root_skill_repo


def _write_global_profile(home: Path, name: str, body: dict) -> None:
    """Author a source-bearing global profile file at ~/.skillpod/profiles/."""
    root = home / ".skillpod" / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.yml").write_text(
        yaml.safe_dump({"version": 1, "profile": body}, sort_keys=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Model normalisation
# ---------------------------------------------------------------------------


def test_skills_accept_bare_string_and_object_form() -> None:
    f = GlobalProfileFile.model_validate(
        {
            "version": 1,
            "profile": {
                "agents": ["claude"],
                "skills": ["audit", {"name": "polish", "source": "o/r", "ref": "main"}],
            },
        }
    )
    audit, polish = f.profile.skills
    assert (audit.name, audit.source) == ("audit", None)
    assert (polish.name, polish.source, polish.ref) == ("polish", "o/r", "main")


def test_as_profile_entry_projects_to_names_only() -> None:
    f = GlobalProfileFile.model_validate(
        {"version": 1, "profile": {"skills": [{"name": "a", "source": "x/y"}, "b"]}}
    )
    entry = f.as_profile_entry()
    assert entry.skills == ["a", "b"]


def test_duplicate_skills_rejected() -> None:
    with pytest.raises(Exception):
        GlobalProfileFile.model_validate(
            {"version": 1, "profile": {"skills": ["a", "a"]}}
        )


def test_load_global_profile_body_reads_inline_source(tmp_path: Path) -> None:
    _write_global_profile(
        tmp_path,
        "dev",
        {"agents": ["claude"], "skills": [{"name": "audit", "source": "o/r"}]},
    )
    body = load_global_profile_body("dev", home=tmp_path)
    assert body is not None
    assert body.skills[0].source == "o/r"


# ---------------------------------------------------------------------------
# plan_apply classification
# ---------------------------------------------------------------------------


def test_plan_classifies_missing_with_source_as_download(tmp_path: Path) -> None:
    body = GlobalProfileBody.model_validate(
        {"agents": ["claude"], "skills": [{"name": "audit", "source": "o/r"}]}
    )
    plan = plan_apply(body, home=tmp_path)
    assert [s.name for s in plan.to_download] == ["audit"]
    assert plan.unresolved == []
    assert plan.has_changes


def test_plan_classifies_missing_without_source_as_unresolved(tmp_path: Path) -> None:
    body = GlobalProfileBody.model_validate({"skills": ["audit"]})
    plan = plan_apply(body, home=tmp_path)
    assert plan.unresolved == ["audit"]
    assert plan.to_download == []


def test_plan_classifies_cached_unlinked_as_link(tmp_path: Path) -> None:
    # Pre-create the cache entry but no fan-out.
    (global_skill_dir("audit", tmp_path)).mkdir(parents=True)
    body = GlobalProfileBody.model_validate(
        {"agents": ["claude"], "skills": [{"name": "audit", "source": "o/r"}]}
    )
    plan = plan_apply(body, home=tmp_path)
    assert plan.to_link == ["audit"]
    assert plan.to_download == []


# ---------------------------------------------------------------------------
# End-to-end apply with a real git source
# ---------------------------------------------------------------------------


def test_apply_downloads_and_fans_out(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    body = GlobalProfileBody.model_validate(
        {"agents": ["claude", "codex"], "skills": [{"name": "audit", "source": str(repo)}]}
    )
    plan = plan_apply(body, home=home)
    report = execute_apply(body, plan, force=True, home=home)

    assert report.downloaded == ["audit"]
    # Cache copy is a real directory.
    assert global_skill_dir("audit", home).is_dir()
    # Fan-out symlinks exist and are managed, only for the declared agents.
    for agent in ("claude", "codex"):
        link = global_agent_skill_dir(agent, "audit", home)
        assert is_managed_global_fanout(link, "audit", home)
    assert not global_agent_skill_dir("gemini", "audit", home).exists()


def test_switching_profile_unlinks_previous_keeps_cache(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"

    # Apply profile A (audit active).
    body_a = GlobalProfileBody.model_validate(
        {"agents": ["claude"], "skills": [{"name": "audit", "source": str(repo)}]}
    )
    execute_apply(body_a, plan_apply(body_a, home=home), force=True, home=home)
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )

    # Apply profile B (empty) — audit should be unlinked but cache kept.
    body_b = GlobalProfileBody.model_validate({"agents": ["claude"], "skills": []})
    report = execute_apply(body_b, plan_apply(body_b, home=home), force=True, home=home)

    assert report.unlinked == ["audit"]
    assert not global_agent_skill_dir("claude", "audit", home).exists()
    assert global_skill_dir("audit", home).is_dir()  # cache preserved


def test_narrowing_agents_prunes_dropped_agent(tmp_path: Path) -> None:
    """A re-apply that narrows a kept skill's agents unlinks the dropped ones."""
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"

    # Profile A: audit on claude + codex.
    body_a = GlobalProfileBody.model_validate(
        {"agents": ["claude", "codex"], "skills": [{"name": "audit", "source": str(repo)}]}
    )
    execute_apply(body_a, plan_apply(body_a, home=home), force=True, home=home)
    assert is_managed_global_fanout(
        global_agent_skill_dir("codex", "audit", home), "audit", home
    )

    # Profile B: same skill, but narrowed to claude only.
    body_b = GlobalProfileBody.model_validate(
        {"agents": ["claude"], "skills": [{"name": "audit", "source": str(repo)}]}
    )
    execute_apply(body_b, plan_apply(body_b, home=home), force=True, home=home)

    # audit stays on claude, is pruned from codex, cache intact.
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )
    assert not global_agent_skill_dir("codex", "audit", home).exists()
    assert global_skill_dir("audit", home).is_dir()


def test_apply_does_not_clobber_unmanaged_fanout_dir(tmp_path: Path) -> None:
    """A hand-placed real directory at a fan-out target is never deleted."""
    from skillpod.installer.errors import InstallConflict

    home = tmp_path / "home"
    # Cache has 'audit' so the profile classifies it as to_link (not download).
    global_skill_dir("audit", home).mkdir(parents=True)
    # User has hand-placed a real directory (not a managed symlink) at the target.
    target = global_agent_skill_dir("claude", "audit", home)
    target.mkdir(parents=True)
    marker = target / "user_data.txt"
    marker.write_text("precious", encoding="utf-8")

    body = GlobalProfileBody.model_validate({"agents": ["claude"], "skills": ["audit"]})
    plan = plan_apply(body, home=home)
    with pytest.raises(InstallConflict):
        execute_apply(body, plan, force=False, home=home)

    # The user's content must survive the failed apply.
    assert marker.read_text(encoding="utf-8") == "precious"


# ---------------------------------------------------------------------------
# CLI: switch --scope global (reconcile), --dry-run preview
# ---------------------------------------------------------------------------


def _switch(name: str, tmp_path: Path, home: Path, **kw: object) -> None:
    """Call switch.run for the global scope outside any project."""
    switch.run(
        name,
        "global",
        project_root=tmp_path,
        manifest_path=tmp_path / "skillfile.yml",  # absent → no project guard
        json_output=False,
        home=home,
        **kw,
    )


def test_switch_global_dry_run_does_not_change_state(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    _write_global_profile(
        home, "dev", {"agents": ["claude"], "skills": [{"name": "audit", "source": str(repo)}]}
    )

    _switch("dev", tmp_path, home, dry_run=True)
    assert not global_skill_dir("audit", home).exists()
    assert not global_agent_skill_dir("claude", "audit", home).exists()


def test_switch_global_materialises_and_sets_active(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    _write_global_profile(
        home, "dev", {"agents": ["claude"], "skills": [{"name": "audit", "source": str(repo)}]}
    )

    _switch("dev", tmp_path, home)
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )
    active = (home / ".skillpod" / "active-profile").read_text(encoding="utf-8").strip()
    assert active == "dev"


def test_switch_global_unknown_profile_exits_nonzero(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        _switch("nope", tmp_path, tmp_path / "home")
    assert exc_info.value.exit_code == 1
