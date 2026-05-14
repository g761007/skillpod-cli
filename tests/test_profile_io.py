"""Tests for profile I/O — global file CRUD and project YAML mutations."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from skillpod.manifest.models import ProfileEntry
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import (
    create_project_profile,
    get_project_profile,
    list_global_profiles,
    list_project_profiles,
    load_global_profile,
    update_project_profile_skills,
    write_global_profile,
)

# ---- global profile round-trip -----------------------------------------------


def test_write_read_global_profile_round_trip(tmp_path: Path) -> None:
    entry = ProfileEntry(type="role", agents=["claude"], skills=["audit", "review"])
    write_global_profile("reviewer", entry, home=tmp_path)

    loaded = load_global_profile("reviewer", home=tmp_path)

    assert loaded is not None
    assert loaded.type == "role"
    assert loaded.agents == ["claude"]
    assert loaded.skills == ["audit", "review"]


def test_load_global_profile_not_found_returns_none(tmp_path: Path) -> None:
    assert load_global_profile("nonexistent", home=tmp_path) is None


def test_write_global_profile_invalid_name_raises(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="invalid"):
        write_global_profile("bad name!", ProfileEntry(), home=tmp_path)


def test_write_global_profile_empty_profile(tmp_path: Path) -> None:
    write_global_profile("empty", ProfileEntry(), home=tmp_path)

    loaded = load_global_profile("empty", home=tmp_path)

    assert loaded is not None
    assert loaded.type is None
    assert loaded.agents == []
    assert loaded.skills == []


# ---- list_global_profiles ----------------------------------------------------


def test_list_global_profiles_empty(tmp_path: Path) -> None:
    assert list_global_profiles(home=tmp_path) == []


def test_list_global_profiles_populated(tmp_path: Path) -> None:
    write_global_profile("alpha", ProfileEntry(), home=tmp_path)
    write_global_profile("beta", ProfileEntry(), home=tmp_path)

    assert list_global_profiles(home=tmp_path) == ["alpha", "beta"]


# ---- project profile CRUD ----------------------------------------------------


def _write_manifest(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def test_create_project_profile_writes_yaml(tmp_path: Path) -> None:
    mf = tmp_path / "skillfile.yml"
    _write_manifest(mf, "version: 1\n")

    create_project_profile("reviewer", ProfileEntry(type="role"), mf)

    raw = yaml.safe_load(mf.read_text(encoding="utf-8"))
    assert "reviewer" in raw["profiles"]
    assert raw["profiles"]["reviewer"]["type"] == "role"


def test_create_project_profile_duplicate_raises(tmp_path: Path) -> None:
    mf = tmp_path / "skillfile.yml"
    _write_manifest(mf, "version: 1\n")
    create_project_profile("reviewer", ProfileEntry(), mf)

    with pytest.raises(ProfileError, match="already exists"):
        create_project_profile("reviewer", ProfileEntry(), mf)


def test_get_project_profile_returns_none_for_missing(tmp_path: Path) -> None:
    from skillpod.manifest.loader import loads

    manifest = loads("version: 1\n")
    assert get_project_profile(manifest, "nonexistent") is None


def test_list_project_profiles_empty_and_populated(tmp_path: Path) -> None:
    from skillpod.manifest.loader import loads

    empty = loads("version: 1\n")
    assert list_project_profiles(empty) == []

    mf = tmp_path / "skillfile.yml"
    _write_manifest(
        mf,
        """
        version: 1
        profiles:
          alpha:
            type: role
          beta: {}
        """,
    )
    from skillpod.manifest.loader import load

    manifest = load(mf)
    assert list_project_profiles(manifest) == ["alpha", "beta"]


def test_update_project_profile_skills(tmp_path: Path) -> None:
    mf = tmp_path / "skillfile.yml"
    _write_manifest(mf, "version: 1\n")
    create_project_profile("reviewer", ProfileEntry(skills=["audit"]), mf)

    update_project_profile_skills("reviewer", ["audit", "review"], mf)

    raw = yaml.safe_load(mf.read_text(encoding="utf-8"))
    assert raw["profiles"]["reviewer"]["skills"] == ["audit", "review"]


def test_update_project_profile_skills_not_found_raises(tmp_path: Path) -> None:
    mf = tmp_path / "skillfile.yml"
    _write_manifest(mf, "version: 1\n")

    with pytest.raises(ProfileError, match="not found"):
        update_project_profile_skills("nobody", ["audit"], mf)
