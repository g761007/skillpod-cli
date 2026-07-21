"""Tests for `skillpod global update`.

Phase 2 of `plans/2026-07-21-recommendation-model.md`. The defining constraint
is that a global skill set is heterogeneous and largely uncurated: most entries
cannot be refreshed at all, and the command has to stay useful anyway.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app
from skillpod.installer import global_update as global_update_mod
from skillpod.installer.global_install import install_global
from skillpod.installer.global_record import read_global_record, write_global_record
from skillpod.installer.global_update import execute_update, plan_update
from skillpod.installer.paths import global_agent_skill_dir, global_skill_dir
from skillpod.record.models import InstallRecord, SkillRecord
from skillpod.sources.discovery import discover_skills
from skillpod.sources.git import populate_cache, resolve_ref
from skillpod.sources.spec import parse_source_spec
from tests._git_fixtures import _git, make_root_skill_repo

_COMMIT = "a" * 40


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _install_from(url: str, home: Path, *, agents: list[str] | None = None) -> None:
    spec = parse_source_spec(url)
    assert spec is not None
    root = populate_cache(spec.url_or_path, resolve_ref(spec.url_or_path, spec.ref or "main"))
    discovered = discover_skills(root, root_name=spec.derived_name)
    install_global(spec, discovered, agents=agents or ["claude"], force=True, home=home)


def _commit_more(repo: Path, text: str) -> str:
    (repo / "SKILL.md").write_text(f"---\ndescription: audit\n---\n{text}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "move upstream")
    return _git(repo, "rev-parse", "HEAD").strip()


# ---- the happy path --------------------------------------------------------


def test_update_pulls_a_moved_upstream(isolated_env: Path, tmp_path: Path) -> None:
    repo, first = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    _install_from(repo.as_uri(), isolated_env)
    second = _commit_more(repo, "revised guidance")

    plan, missing = plan_update(home=isolated_env)
    assert missing == []
    assert [u.name for u in plan.to_update] == ["audit"]
    assert plan.to_update[0].from_commit == first
    assert plan.to_update[0].to_commit == second

    report = execute_update(plan, home=isolated_env)

    assert [u.name for u in report.updated] == ["audit"]
    assert report.failed == []
    # Content on disk is the new revision, and the record agrees.
    body = (global_skill_dir("audit", isolated_env) / "SKILL.md").read_text(encoding="utf-8")
    assert "revised guidance" in body
    assert read_global_record(isolated_env).installed["audit"].commit == second


def test_unmoved_upstream_is_reported_as_current(isolated_env: Path, tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    _install_from(repo.as_uri(), isolated_env)

    plan, _missing = plan_update(home=isolated_env)

    assert plan.current == ["audit"]
    assert plan.to_update == []


def test_update_puts_the_skill_back_only_where_it_was(
    isolated_env: Path, tmp_path: Path
) -> None:
    """Refreshing must not quietly fan a skill out to agents that never had it."""
    repo, _first = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    _install_from(repo.as_uri(), isolated_env, agents=["claude"])
    _commit_more(repo, "revised")

    plan, _missing = plan_update(home=isolated_env)
    execute_update(plan, home=isolated_env)

    assert global_agent_skill_dir("claude", "audit", isolated_env).exists()
    assert not global_agent_skill_dir("codex", "audit", isolated_env).exists()


# ---- the population that cannot be updated ---------------------------------


def test_unknown_and_local_skills_are_reported_not_failed(isolated_env: Path) -> None:
    """37 of the author's 88 global skills have no recoverable origin and 33
    more are local directories. Refusing to run because of them would make the
    command useless on exactly the set it exists for."""
    global_skill_dir("mystery", isolated_env).mkdir(parents=True)
    write_global_record(
        InstallRecord(
            installed={
                "mystery": SkillRecord(kind="unknown"),
                "handmade": SkillRecord(kind="local", source="/srv/skills/handmade"),
            }
        ),
        isolated_env,
    )
    global_skill_dir("handmade", isolated_env).mkdir(parents=True)

    plan, _missing = plan_update(home=isolated_env)

    assert plan.skipped_unknown == ["mystery"]
    assert plan.skipped_local == ["handmade"]
    assert plan.to_update == []


def test_unreachable_remote_does_not_stop_the_others(
    isolated_env: Path, tmp_path: Path
) -> None:
    """One dead remote out of many must not abort the whole run."""
    repo, _first = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    _install_from(repo.as_uri(), isolated_env)
    _commit_more(repo, "revised")

    record = read_global_record(isolated_env)
    record.installed["ghost"] = SkillRecord(
        kind="git",
        source="https://this-host-does-not-exist.invalid/r.git",
        ref="main",
        commit=_COMMIT,
    )
    write_global_record(record, isolated_env)
    global_skill_dir("ghost", isolated_env).mkdir(parents=True)

    plan, _missing = plan_update(home=isolated_env)

    assert [name for name, _reason in plan.unreachable] == ["ghost"]
    assert [u.name for u in plan.to_update] == ["audit"]


def test_shorthand_source_is_expanded_before_git_sees_it(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recovered source is usually the `owner/repo` shorthand, which git
    itself cannot resolve.

    Regression: passing it through unexpanded made *every* GitHub-sourced skill
    report as unreachable. Every unit test here uses a `file://` URL, which is
    already a valid remote — so the defect only surfaced when running against a
    real global skill set. This test pins the expansion without touching the
    network.
    """
    seen: list[str] = []

    def fake_default_branch(url: str) -> str:
        seen.append(url)
        return "main"

    def fake_resolve_ref(url: str, ref: str) -> str:
        seen.append(url)
        return "b" * 40

    monkeypatch.setattr(global_update_mod, "resolve_default_branch", fake_default_branch)
    monkeypatch.setattr(global_update_mod, "resolve_ref", fake_resolve_ref)

    global_skill_dir("audit", isolated_env).mkdir(parents=True)
    write_global_record(
        InstallRecord(
            installed={
                "audit": SkillRecord(
                    kind="git", source="anthropics/skills", commit=_COMMIT
                )
            }
        ),
        isolated_env,
    )

    plan, _missing = plan_update(home=isolated_env)

    assert seen == ["https://github.com/anthropics/skills"] * 2
    assert plan.unreachable == []
    assert [u.name for u in plan.to_update] == ["audit"]
    assert plan.to_update[0].source == "https://github.com/anthropics/skills"


def test_unreachable_reason_is_a_single_line(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git failures are multi-line; a report table cannot hold them."""

    def explode(url: str) -> str:
        raise RuntimeError("fatal: repository not found\nfatal: could not read\nmore")

    monkeypatch.setattr(global_update_mod, "resolve_default_branch", explode)

    global_skill_dir("audit", isolated_env).mkdir(parents=True)
    write_global_record(
        InstallRecord(
            installed={"audit": SkillRecord(kind="git", source="o/r", commit=_COMMIT)}
        ),
        isolated_env,
    )

    plan, _missing = plan_update(home=isolated_env)

    [(name, reason)] = plan.unreachable
    assert name == "audit"
    assert "\n" not in reason
    assert reason == "fatal: repository not found"


# ---- selection and preview -------------------------------------------------


def test_named_subset_leaves_other_skills_alone(isolated_env: Path, tmp_path: Path) -> None:
    audit, _ = make_root_skill_repo(tmp_path / "a", repo_name="audit")
    polish, _ = make_root_skill_repo(tmp_path / "b", repo_name="polish")
    _install_from(audit.as_uri(), isolated_env)
    _install_from(polish.as_uri(), isolated_env)
    _commit_more(audit, "revised")
    _commit_more(polish, "revised")

    plan, _missing = plan_update(names=["audit"], home=isolated_env)

    assert [u.name for u in plan.to_update] == ["audit"]


def test_naming_a_skill_that_is_not_installed_is_reported(isolated_env: Path) -> None:
    plan, missing = plan_update(names=["nope"], home=isolated_env)
    assert missing == ["nope"]
    assert plan.to_update == []


def test_dry_run_downloads_nothing(
    runner: CliRunner, isolated_env: Path, tmp_path: Path
) -> None:
    repo, first = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    _install_from(repo.as_uri(), isolated_env)
    _commit_more(repo, "revised")

    result = runner.invoke(app, ["global", "update", "--dry-run", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert [p["name"] for p in payload["pending"]] == ["audit"]
    # Untouched on disk.
    assert read_global_record(isolated_env).installed["audit"].commit == first
    body = (global_skill_dir("audit", isolated_env) / "SKILL.md").read_text(encoding="utf-8")
    assert "revised" not in body


# ---- CLI surface -----------------------------------------------------------


def test_dry_run_does_not_even_write_the_record(
    runner: CliRunner, isolated_env: Path
) -> None:
    """`--dry-run` promises to touch nothing.

    Planning backfills the record so it can classify pre-existing skills, and
    that write is easy to overlook because its contents only restate what is
    already on disk — but a dry run that creates a file is still a dry run that
    lied.
    """
    global_skill_dir("mystery", isolated_env).mkdir(parents=True)
    record_file = isolated_env / ".skillpod" / "installed.yml"
    assert not record_file.exists()

    result = runner.invoke(app, ["global", "update", "--dry-run", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["skipped_unknown"] == ["mystery"]
    assert not record_file.exists()


def test_cli_exits_zero_with_nothing_updatable(runner: CliRunner, isolated_env: Path) -> None:
    global_skill_dir("mystery", isolated_env).mkdir(parents=True)

    result = runner.invoke(app, ["global", "update"])

    assert result.exit_code == 0
    assert "origin unknown" in result.stdout


def test_upgrade_is_an_alias(runner: CliRunner, isolated_env: Path) -> None:
    """`upgrade` is the word the author reached for first; it keeps working
    even though `update` is the documented name."""
    global_skill_dir("mystery", isolated_env).mkdir(parents=True)

    updated = runner.invoke(app, ["global", "update", "--json"])
    upgraded = runner.invoke(app, ["global", "upgrade", "--json"])

    assert upgraded.exit_code == updated.exit_code == 0
    assert json.loads(upgraded.stdout) == json.loads(updated.stdout)


def test_backfill_runs_first_so_pre_existing_skills_are_classified(
    runner: CliRunner, isolated_env: Path
) -> None:
    """A user upgrading skillpod has skills but no record. `global update` must
    still say something useful about them rather than 'nothing installed'."""
    for name in ("alpha", "beta"):
        global_skill_dir(name, isolated_env).mkdir(parents=True)

    result = runner.invoke(app, ["global", "update", "--json"])

    assert result.exit_code == 0
    assert sorted(json.loads(result.stdout)["skipped_unknown"]) == ["alpha", "beta"]
    # And the record now exists, so the next run starts from a known state.
    assert set(read_global_record(isolated_env).installed) == {"alpha", "beta"}
