"""Tests for profile_export and profile_import command modules."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
import yaml

from skillpod.cli.commands import profile_export, profile_import
from skillpod.profile.io import get_project_profile, load_global_profile


def _write_manifest(tmp_path: Path, text: str) -> Path:
    mf = tmp_path / "skillfile.yml"
    mf.write_text(text, encoding="utf-8")
    return mf


_SIMPLE_MANIFEST = (
    "version: 1\n"
    "skills: [audit, review]\n"
    "profiles:\n"
    "  reviewer:\n"
    "    type: role\n"
    "    skills: [audit, review]\n"
)


# ---- export -------------------------------------------------------------------


def test_export_produces_valid_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(tmp_path, _SIMPLE_MANIFEST)

    profile_export.run(
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
    )

    out = capsys.readouterr().out
    data = yaml.safe_load(out)
    assert data["skillpod_profile_export"] == "1"
    assert data["source_scope"] == "project"
    assert data["profile"]["name"] == "reviewer"
    assert data["profile"]["type"] == "role"
    assert "audit" in data["profile"]["skills"]
    assert "review" in data["profile"]["skills"]


def test_export_to_file(tmp_path: Path) -> None:
    mf = _write_manifest(tmp_path, _SIMPLE_MANIFEST)
    out_file = tmp_path / "reviewer.yml"

    profile_export.run(
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
        out=out_file,
    )

    assert out_file.is_file()
    data = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert data["skillpod_profile_export"] == "1"
    assert data["profile"]["name"] == "reviewer"


def test_export_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(tmp_path, _SIMPLE_MANIFEST)

    profile_export.run(
        "reviewer",
        project_root=tmp_path,
        manifest_path=mf,
        json_output=True,
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["skillpod_profile_export"] == "1"
    assert payload["profile"]["name"] == "reviewer"


def test_export_unknown_profile_raises(tmp_path: Path) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: [audit]\n")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        profile_export.run(
            "nonexistent",
            project_root=tmp_path,
            manifest_path=mf,
            json_output=False,
        )
    assert exc_info.value.exit_code == 1


# ---- import -------------------------------------------------------------------


def _make_export_file(tmp_path: Path, name: str = "reviewer") -> Path:
    """Create a valid export YAML file and return its path."""
    data = {
        "skillpod_profile_export": "1",
        "exported_at": "2026-05-15T00:00:00Z",
        "source_scope": "project",
        "profile": {
            "name": name,
            "type": "role",
            "skills": ["audit", "review"],
            "agents": [],
        },
    }
    path = tmp_path / f"{name}_export.yml"
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def test_import_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: [audit, review]\n")
    export_file = _make_export_file(tmp_path, "reviewer")

    profile_import.run(
        export_file,
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
    )

    out = capsys.readouterr().out
    assert "reviewer" in out

    # Check the imported sidecar file was written
    imported_path = tmp_path / ".skillpod" / "imported" / "reviewer.yml"
    assert imported_path.is_file()
    data = yaml.safe_load(imported_path.read_text(encoding="utf-8"))
    assert data["profile"]["skills"] == ["audit", "review"]

    # Verify get_project_profile can find it via project_root
    from skillpod.manifest.loader import loads
    manifest = loads("version: 1\nskills: [audit, review]\n")
    entry = get_project_profile(manifest, "reviewer", project_root=tmp_path)
    assert entry is not None
    assert set(entry.skills) == {"audit", "review"}


def test_import_rename(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: [audit, review]\n")
    export_file = _make_export_file(tmp_path, "reviewer")

    profile_import.run(
        export_file,
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
        rename="myreviewer",
    )

    out = capsys.readouterr().out
    assert "myreviewer" in out

    imported_path = tmp_path / ".skillpod" / "imported" / "myreviewer.yml"
    assert imported_path.is_file()


def test_import_invalid_file_raises(tmp_path: Path) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: []\n")
    bad_file = tmp_path / "bad.yml"
    bad_file.write_text("- not: a\n  mapping\n", encoding="utf-8")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        profile_import.run(
            bad_file,
            project_root=tmp_path,
            manifest_path=mf,
            json_output=False,
        )
    assert exc_info.value.exit_code == 1


def test_import_missing_header_raises(tmp_path: Path) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: []\n")
    no_header = tmp_path / "no_header.yml"
    no_header.write_text(
        "profile:\n  name: reviewer\n  skills: [audit]\n",
        encoding="utf-8",
    )

    with pytest.raises(click.exceptions.Exit) as exc_info:
        profile_import.run(
            no_header,
            project_root=tmp_path,
            manifest_path=mf,
            json_output=False,
        )
    assert exc_info.value.exit_code == 1


def test_import_global_scope(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mf = _write_manifest(tmp_path, "version: 1\nskills: [audit, review]\n")
    export_file = _make_export_file(tmp_path, "reviewer")
    home = tmp_path / "home"
    home.mkdir()

    profile_import.run(
        export_file,
        project_root=tmp_path,
        manifest_path=mf,
        json_output=False,
        is_global=True,
        home=home,
    )

    out = capsys.readouterr().out
    assert "global" in out

    # The profile should be loadable via load_global_profile
    entry = load_global_profile("reviewer", home)
    assert entry is not None
    assert set(entry.skills) == {"audit", "review"}
