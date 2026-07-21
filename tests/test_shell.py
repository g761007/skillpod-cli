"""Tests for skillpod shell command module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.exceptions import Exit as ClickExit

from skillpod.cli.commands import shell as shell_mod
from tests._env import set_home

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "skillfile.yml"
    p.write_text(content)
    return p


_MANIFEST_DEV = """\
version: 1
skills:
  - audit
  - review
profiles:
  dev:
    skills: [audit]
"""


# ---------------------------------------------------------------------------
# test_shell_builds_correct_env
# ---------------------------------------------------------------------------

def test_shell_builds_correct_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _make_manifest(tmp_path, _MANIFEST_DEV)

    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> MagicMock:
        captured["args"] = args
        captured["env"] = dict(kwargs.get("env", {}))
        return MagicMock(returncode=0)

    set_home(monkeypatch, tmp_path)
    monkeypatch.delenv("SKILLPOD_SHELL_DEPTH", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)

    shell_mod.run(
        "dev",
        project_root=tmp_path,
        manifest_path=manifest_path,
        json_output=False,
        home=tmp_path,
    )

    assert captured["env"]["SKILLPOD_ACTIVE_PROFILE"] == "dev"
    assert captured["env"]["SKILLPOD_SHELL_DEPTH"] == "1"


# ---------------------------------------------------------------------------
# test_shell_rejects_nested_invocation
# ---------------------------------------------------------------------------

def test_shell_rejects_nested_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _make_manifest(tmp_path, _MANIFEST_DEV)

    monkeypatch.setenv("SKILLPOD_SHELL_DEPTH", "1")
    set_home(monkeypatch, tmp_path)

    with pytest.raises(ClickExit) as exc_info:
        shell_mod.run(
            "dev",
            project_root=tmp_path,
            manifest_path=manifest_path,
            json_output=False,
            home=tmp_path,
        )
    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# test_shell_unknown_profile_raises
# ---------------------------------------------------------------------------

def test_shell_unknown_profile_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _make_manifest(tmp_path, _MANIFEST_DEV)

    monkeypatch.delenv("SKILLPOD_SHELL_DEPTH", raising=False)
    set_home(monkeypatch, tmp_path)

    with pytest.raises(ClickExit) as exc_info:
        shell_mod.run(
            "nonexistent",
            project_root=tmp_path,
            manifest_path=manifest_path,
            json_output=False,
            home=tmp_path,
        )
    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# test_shell_spawns_correct_executable
# ---------------------------------------------------------------------------

def test_shell_spawns_correct_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _make_manifest(tmp_path, _MANIFEST_DEV)

    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> MagicMock:
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        return MagicMock(returncode=0)

    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.delenv("SKILLPOD_SHELL_DEPTH", raising=False)
    set_home(monkeypatch, tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    shell_mod.run(
        "dev",
        project_root=tmp_path,
        manifest_path=manifest_path,
        json_output=False,
        home=tmp_path,
    )

    assert captured["args"] == ["/bin/bash"]


# ---------------------------------------------------------------------------
# test_shell_sets_ps1_prefix
# ---------------------------------------------------------------------------

def test_shell_sets_ps1_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _make_manifest(tmp_path, _MANIFEST_DEV)

    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> MagicMock:
        captured["env"] = dict(kwargs.get("env", {}))
        return MagicMock(returncode=0)

    monkeypatch.setenv("PS1", "\\u@\\h $ ")
    monkeypatch.delenv("SKILLPOD_SHELL_DEPTH", raising=False)
    set_home(monkeypatch, tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    shell_mod.run(
        "dev",
        project_root=tmp_path,
        manifest_path=manifest_path,
        json_output=False,
        home=tmp_path,
    )

    ps1 = captured["env"].get("PS1", "")
    assert ps1.startswith("[skillpod:dev] ")
