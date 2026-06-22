"""Tests for global profile save (source recovery), --back undo, and URL fetch."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from skillpod.cli.commands import profile_save, switch
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_skill_dir,
    is_managed_global_fanout,
)
from skillpod.profile.fetch import resolve_profile_target
from skillpod.profile.io import load_global_profile_body
from skillpod.profile.snapshot import recover_source, snapshot_current_global
from tests._git_fixtures import make_root_skill_repo

_COMMIT = "a" * 40


def _managed_symlink(home: Path, agent: str, name: str, target: Path) -> None:
    link = global_agent_skill_dir(agent, name, home)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


# ---------------------------------------------------------------------------
# Source recovery
# ---------------------------------------------------------------------------


def test_recover_source_from_github_cache_symlink(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    home = tmp_path / "home"
    # Fake cache layout: <cache>/github.com/anthropics/skills@<commit>/skills/audit
    cache_skill = cache / "github.com" / "anthropics" / f"skills@{_COMMIT}" / "skills" / "audit"
    cache_skill.mkdir(parents=True)
    # ~/.skillpod/skills/audit -> cache skill dir
    install = global_skill_dir("audit", home)
    install.parent.mkdir(parents=True, exist_ok=True)
    install.symlink_to(cache_skill)

    skill = recover_source("audit", home)
    assert skill.name == "audit"
    assert skill.source == "anthropics/skills"  # github → owner/repo shorthand
    assert skill.ref == _COMMIT
    assert skill.subpath == "skills/audit"


def test_recover_source_real_dir_is_name_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    global_skill_dir("audit", home).mkdir(parents=True)  # real dir, no origin
    skill = recover_source("audit", home)
    assert skill.name == "audit"
    assert skill.source is None


def test_snapshot_captures_managed_skills(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    home = tmp_path / "home"
    cache_skill = cache / "github.com" / "anthropics" / f"skills@{_COMMIT}" / "skills" / "audit"
    cache_skill.mkdir(parents=True)
    install = global_skill_dir("audit", home)
    install.parent.mkdir(parents=True, exist_ok=True)
    install.symlink_to(cache_skill)
    _managed_symlink(home, "claude", "audit", install)

    body = snapshot_current_global(home, name="snap")
    assert body.name == "snap"
    assert [s.name for s in body.skills] == ["audit"]
    assert body.skills[0].source == "anthropics/skills"
    assert "claude" in body.agents


# ---------------------------------------------------------------------------
# profile save command
# ---------------------------------------------------------------------------


def test_profile_save_writes_portable_profile(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    home = tmp_path / "home"
    cache_skill = cache / "github.com" / "anthropics" / f"skills@{_COMMIT}" / "skills" / "audit"
    cache_skill.mkdir(parents=True)
    install = global_skill_dir("audit", home)
    install.parent.mkdir(parents=True, exist_ok=True)
    install.symlink_to(cache_skill)
    _managed_symlink(home, "claude", "audit", install)

    profile_save.run("mywork", json_output=False, home=home)

    body = load_global_profile_body("mywork", home)
    assert body is not None
    assert body.skills[0].source == "anthropics/skills"


def test_profile_save_refuses_overwrite_without_yes(tmp_path: Path) -> None:
    import typer

    home = tmp_path / "home"
    (home / ".skillpod" / "profiles").mkdir(parents=True)
    (home / ".skillpod" / "profiles" / "dup.yml").write_text(
        "version: 1\nprofile:\n  skills: []\n", encoding="utf-8"
    )
    with pytest.raises(typer.Exit):
        profile_save.run("dup", json_output=False, home=home)


# ---------------------------------------------------------------------------
# switch --back (single-level undo)
# ---------------------------------------------------------------------------


def _switch(name: str, tmp_path: Path, home: Path, **kw: object) -> None:
    switch.run(
        name,
        "global",
        project_root=tmp_path,
        manifest_path=tmp_path / "skillfile.yml",
        json_output=False,
        home=home,
        **kw,
    )


def test_switch_back_restores_previous_skill_set(tmp_path: Path) -> None:
    repo, _sha = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    home = tmp_path / "home"
    profiles = home / ".skillpod" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "a.yml").write_text(
        f"version: 1\nprofile:\n  agents: [claude]\n  skills:\n    - name: audit\n      source: {repo}\n",
        encoding="utf-8",
    )
    (profiles / "b.yml").write_text(
        "version: 1\nprofile:\n  agents: [claude]\n  skills: []\n", encoding="utf-8"
    )

    _switch("a", tmp_path, home)  # audit active
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )

    _switch("b", tmp_path, home)  # audit unlinked
    assert not global_agent_skill_dir("claude", "audit", home).exists()

    _switch("", tmp_path, home, back=True)  # restore previous (a's set)
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )


def test_switch_back_without_history_errors(tmp_path: Path) -> None:
    import typer

    with pytest.raises(typer.Exit):
        _switch("", tmp_path, tmp_path / "home", back=True)


# ---------------------------------------------------------------------------
# URL target fetch
# ---------------------------------------------------------------------------


@respx.mock
def test_resolve_url_downloads_profile(tmp_path: Path) -> None:
    home = tmp_path / "home"
    url = "https://example.test/developer.yml"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text=(
                "version: 1\n"
                "profile:\n"
                "  name: developer\n"
                "  agents: [claude]\n"
                "  skills:\n"
                "    - name: audit\n"
                "      source: anthropics/skills\n"
            ),
        )
    )
    name, body = resolve_profile_target(url, home=home)
    assert name == "developer"
    assert body.skills[0].source == "anthropics/skills"
    # File was saved locally for reuse.
    assert (home / ".skillpod" / "profiles" / "developer.yml").is_file()


@respx.mock
def test_resolve_url_uses_local_when_present(tmp_path: Path) -> None:
    home = tmp_path / "home"
    profiles = home / ".skillpod" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "developer.yml").write_text(
        "version: 1\nprofile:\n  skills: [local_only]\n", encoding="utf-8"
    )
    # No respx route registered → if it tried to download, it would error.
    name, body = resolve_profile_target(
        "https://example.test/developer.yml", home=home
    )
    assert name == "developer"
    assert [s.name for s in body.skills] == ["local_only"]


def test_resolve_owner_repo_shorthand_builds_raw_url(tmp_path: Path) -> None:
    home = tmp_path / "home"

    @respx.mock
    def _inner() -> None:
        raw = "https://raw.githubusercontent.com/me/profiles/HEAD/dev.yml"
        respx.get(raw).mock(
            return_value=httpx.Response(
                200,
                text="version: 1\nprofile:\n  name: dev\n  skills: [audit]\n",
            )
        )
        name, _body = resolve_profile_target("me/profiles/dev.yml", home=home)
        assert name == "dev"

    _inner()
