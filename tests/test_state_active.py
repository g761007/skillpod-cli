"""Tests for state.active and state.io — active profile read/write/clear per scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillpod.state.active import ENV_VAR, read_active_profile
from skillpod.state.io import clear_active_profile, write_active_profile

# ---- read_active_profile — no state ----------------------------------------


def test_read_active_profile_none_when_no_state(tmp_path: Path) -> None:
    name, scope = read_active_profile(tmp_path)
    assert name is None
    assert scope is None


# ---- project scope ----------------------------------------------------------


def test_write_read_project_scope(tmp_path: Path) -> None:
    write_active_profile("dev", "project", tmp_path)

    name, scope = read_active_profile(tmp_path)

    assert name == "dev"
    assert scope == "project"


def test_project_file_written_to_correct_path(tmp_path: Path) -> None:
    write_active_profile("ci", "project", tmp_path)

    path = tmp_path / ".skillpod" / "active-profile"
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip() == "ci"


# ---- global scope -----------------------------------------------------------


def test_write_read_global_scope(tmp_path: Path) -> None:
    proj = tmp_path / "project"
    proj.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    write_active_profile("reviewer", "global", proj, home=home)

    name, scope = read_active_profile(proj, home=home)

    assert name == "reviewer"
    assert scope == "global"


def test_global_file_written_to_correct_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    write_active_profile("base", "global", tmp_path, home=home)

    path = home / ".skillpod" / "active-profile"
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip() == "base"


# ---- session scope (env var) ------------------------------------------------


def test_session_env_var_takes_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_active_profile("project-prof", "project", tmp_path)
    write_active_profile("global-prof", "global", tmp_path, home=tmp_path)
    monkeypatch.setenv(ENV_VAR, "session-prof")

    name, scope = read_active_profile(tmp_path, home=tmp_path)

    assert name == "session-prof"
    assert scope == "session"


# ---- priority: project beats global ----------------------------------------


def test_project_scope_takes_priority_over_global(tmp_path: Path) -> None:
    write_active_profile("global-prof", "global", tmp_path, home=tmp_path)
    write_active_profile("project-prof", "project", tmp_path)

    name, scope = read_active_profile(tmp_path, home=tmp_path)

    assert name == "project-prof"
    assert scope == "project"


# ---- global fallback when no project file ----------------------------------


def test_global_scope_used_when_no_project_file(tmp_path: Path) -> None:
    proj = tmp_path / "project"
    proj.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    write_active_profile("global-prof", "global", proj, home=home)

    name, scope = read_active_profile(proj, home=home)

    assert name == "global-prof"
    assert scope == "global"


# ---- clear ------------------------------------------------------------------


def test_clear_project_scope_removes_file(tmp_path: Path) -> None:
    write_active_profile("dev", "project", tmp_path)

    removed = clear_active_profile("project", tmp_path)

    assert removed is True
    name, _scope = read_active_profile(tmp_path)
    assert name is None


def test_clear_global_scope_removes_file(tmp_path: Path) -> None:
    write_active_profile("dev", "global", tmp_path, home=tmp_path)

    removed = clear_active_profile("global", tmp_path, home=tmp_path)

    assert removed is True
    name, _scope = read_active_profile(tmp_path, home=tmp_path)
    assert name is None


def test_clear_returns_false_when_nothing_to_clear(tmp_path: Path) -> None:
    removed = clear_active_profile("project", tmp_path)
    assert removed is False


def test_clear_only_removes_target_scope(tmp_path: Path) -> None:
    proj = tmp_path / "project"
    proj.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    write_active_profile("proj-prof", "project", proj)
    write_active_profile("glob-prof", "global", proj, home=home)

    clear_active_profile("project", proj)

    name, scope = read_active_profile(proj, home=home)
    assert name == "glob-prof"
    assert scope == "global"


# ---- invalid scope ----------------------------------------------------------


def test_write_invalid_scope_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported scope"):
        write_active_profile("dev", "bad-scope", tmp_path)


def test_clear_invalid_scope_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported scope"):
        clear_active_profile("bad-scope", tmp_path)
