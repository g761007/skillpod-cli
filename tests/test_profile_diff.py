"""Tests for profile_diff command module."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest

from skillpod.cli.commands import profile_diff


def _write_manifest(tmp_path: Path, text: str) -> Path:
    mf = tmp_path / "skillfile.yml"
    mf.write_text(text, encoding="utf-8")
    return mf


# ---- diff logic ---------------------------------------------------------------


def test_diff_added_removed_common(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(
        tmp_path,
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit, lint]\n"
        "  reviewer:\n"
        "    skills: [audit, review]\n",
    )

    profile_diff.run(
        "dev",
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
    )

    out = capsys.readouterr().out
    assert "+ review" in out
    assert "- lint" in out
    assert "  audit" in out


def test_diff_symmetric(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(
        tmp_path,
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit, lint]\n"
        "  reviewer:\n"
        "    skills: [audit, review]\n",
    )

    profile_diff.run(
        "dev",
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=True,
    )
    payload_ab = json.loads(capsys.readouterr().out)

    profile_diff.run(
        "reviewer",
        "dev",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=True,
    )
    payload_ba = json.loads(capsys.readouterr().out)

    # diff(a,b) added == diff(b,a) removed and vice versa
    assert set(payload_ab["added"]) == set(payload_ba["removed"])
    assert set(payload_ab["removed"]) == set(payload_ba["added"])
    assert set(payload_ab["common"]) == set(payload_ba["common"])


def test_diff_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(
        tmp_path,
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit, lint]\n"
        "  reviewer:\n"
        "    skills: [audit, review]\n",
    )

    profile_diff.run(
        "dev",
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=True,
    )

    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {"added", "removed", "common"}
    assert "review" in payload["added"]
    assert "lint" in payload["removed"]
    assert "audit" in payload["common"]


def test_diff_unknown_profile_raises(tmp_path: Path) -> None:
    mf = _write_manifest(
        tmp_path,
        "version: 1\n"
        "skills: [audit]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit]\n",
    )

    with pytest.raises(click.exceptions.Exit) as exc_info:
        profile_diff.run(
            "dev",
            "nonexistent",
            project_root=tmp_path,
            manifest_path=mf,
            json_output=False,
        )
    assert exc_info.value.exit_code == 1
