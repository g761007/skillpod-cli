"""Unit tests for compose_effective_skillset."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillpod.manifest.loader import loads
from skillpod.manifest.models import ProfileEntry
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import write_global_profile
from skillpod.skillset.compose import compose_effective_skillset
from skillpod.skillset.layers import LayerOrigin


def _manifest(text: str):  # type: ignore[return]
    return loads(text)


# ---- no profile — returns all skills ----------------------------------------


def test_compose_no_profile_returns_all_skills(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\nskills: [audit, review]\n")

    result = compose_effective_skillset(manifest, tmp_path)

    assert [s.name for s in result.skills] == ["audit", "review"]


def test_compose_provenance_no_profile(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\nskills: [audit]\n")

    result = compose_effective_skillset(manifest, tmp_path)

    assert result.provenance["audit"] == LayerOrigin.PROJECT


def test_compose_empty_manifest_no_profile(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\n")

    result = compose_effective_skillset(manifest, tmp_path)

    assert result.skills == []


# ---- project profile filter --------------------------------------------------


def test_compose_project_profile_filters(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit, review]\n"
    )

    result = compose_effective_skillset(manifest, tmp_path, profile_name="reviewer")

    assert [s.name for s in result.skills] == ["audit", "review"]


def test_compose_project_profile_provenance(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
    )

    result = compose_effective_skillset(manifest, tmp_path, profile_name="reviewer")

    assert result.provenance["audit"] == LayerOrigin.PROFILE_FILTER
    assert "review" not in result.provenance


def test_compose_project_profile_unknown_skill_raises(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [does-not-exist]\n"
    )

    with pytest.raises(ProfileError, match="unknown skill"):
        compose_effective_skillset(manifest, tmp_path, profile_name="reviewer")


def test_compose_profile_not_found_raises(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\nskills: [audit]\n")

    with pytest.raises(ProfileError, match="not found"):
        compose_effective_skillset(manifest, tmp_path, profile_name="nonexistent")


# ---- global profile filter ---------------------------------------------------


def test_compose_global_profile_used_as_fallback(tmp_path: Path) -> None:
    write_global_profile(
        "g-reviewer", ProfileEntry(skills=["audit"]), home=tmp_path
    )
    manifest = _manifest("version: 1\nskills: [audit, review]\n")

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="g-reviewer", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["audit"]


def test_compose_project_profile_takes_priority_over_global(tmp_path: Path) -> None:
    write_global_profile(
        "reviewer", ProfileEntry(skills=["audit"]), home=tmp_path
    )
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [review]\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["review"]


def test_compose_empty_profile_returns_no_skills(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "profiles:\n"
        "  empty: {}\n"
    )

    result = compose_effective_skillset(manifest, tmp_path, profile_name="empty")

    assert result.skills == []
