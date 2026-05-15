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


# ---- activation policy -------------------------------------------------------


def test_activation_strict_uses_project_profile(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: strict\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["audit"]
    assert result.provenance["audit"] == LayerOrigin.PROFILE_FILTER


def test_activation_strict_rejects_global_profile(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["audit"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "activation:\n"
        "  mode: strict\n"
    )

    with pytest.raises(ProfileError, match="strict mode"):
        compose_effective_skillset(
            manifest, tmp_path, profile_name="reviewer", home=tmp_path
        )


def test_activation_strict_warns_when_global_blocked(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["audit"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "activation:\n"
        "  mode: strict\n"
    )

    with pytest.warns(UserWarning, match="strict activation policy"):
        with pytest.raises(ProfileError):
            compose_effective_skillset(
                manifest, tmp_path, profile_name="reviewer", home=tmp_path
            )


def test_activation_merge_unions_project_and_global_skills(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["review"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: merge\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert sorted(s.name for s in result.skills) == ["audit", "review"]


def test_activation_merge_provenance_distinguishes_layers(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["review"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: merge\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert result.provenance["audit"] == LayerOrigin.PROFILE_FILTER
    assert result.provenance["review"] == LayerOrigin.GLOBAL_PROFILE_FILTER


def test_activation_merge_project_only_when_no_global(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: merge\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["audit"]


def test_activation_fallback_uses_project_first(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["review"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: fallback\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="reviewer", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["audit"]
    assert result.provenance["audit"] == LayerOrigin.PROFILE_FILTER


def test_activation_fallback_uses_global_when_no_project(tmp_path: Path) -> None:
    write_global_profile("g-rev", ProfileEntry(skills=["review"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "activation:\n"
        "  mode: fallback\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="g-rev", home=tmp_path
    )

    assert [s.name for s in result.skills] == ["review"]
    assert result.provenance["review"] == LayerOrigin.GLOBAL_PROFILE_FILTER


def test_activation_fallback_warning_in_result(tmp_path: Path) -> None:
    write_global_profile("g-rev", ProfileEntry(skills=["review"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [review]\n"
        "activation:\n"
        "  mode: fallback\n"
    )

    result = compose_effective_skillset(
        manifest, tmp_path, profile_name="g-rev", home=tmp_path
    )

    assert len(result.warnings) == 1
    assert "fallback" in result.warnings[0]


def test_activation_manual_ignores_default_profile_when_no_explicit(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "activation:\n"
        "  mode: fallback\n"
        "  default_profile: reviewer\n"
    )

    # mode=fallback auto-applies default_profile; manual would not
    result = compose_effective_skillset(manifest, tmp_path, home=tmp_path)

    assert [s.name for s in result.skills] == ["audit"]


def test_activation_inherit_global_false_blocks_global(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["audit"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "activation:\n"
        "  mode: fallback\n"
        "  inherit_global: false\n"
    )

    with pytest.raises(ProfileError, match="not found"):
        compose_effective_skillset(
            manifest, tmp_path, profile_name="reviewer", home=tmp_path
        )


def test_activation_ignore_global_overrides_inherit_global(tmp_path: Path) -> None:
    write_global_profile("reviewer", ProfileEntry(skills=["audit"]), home=tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "activation:\n"
        "  mode: fallback\n"
        "  inherit_global: true\n"
    )

    with pytest.raises(ProfileError, match="not found"):
        compose_effective_skillset(
            manifest, tmp_path, profile_name="reviewer", home=tmp_path,
            ignore_global=True,
        )


def test_activation_no_warnings_in_base_only_result(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\nskills: [audit]\n")

    result = compose_effective_skillset(manifest, tmp_path)

    assert result.warnings == ()


# ---- state active profile integration ---------------------------------------


def test_compose_uses_state_active_profile_when_no_explicit_profile(
    tmp_path: Path,
) -> None:
    from skillpod.state.io import write_active_profile

    write_active_profile("reviewer", "project", tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
    )

    result = compose_effective_skillset(manifest, tmp_path)

    assert [s.name for s in result.skills] == ["audit"]


def test_compose_explicit_profile_name_overrides_state(tmp_path: Path) -> None:
    from skillpod.state.io import write_active_profile

    write_active_profile("reviewer", "project", tmp_path)
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  reviewer:\n"
        "    skills: [audit]\n"
        "  ci:\n"
        "    skills: [review]\n"
    )

    result = compose_effective_skillset(manifest, tmp_path, profile_name="ci")

    assert [s.name for s in result.skills] == ["review"]


def test_compose_no_state_returns_all_skills_unchanged(tmp_path: Path) -> None:
    manifest = _manifest("version: 1\nskills: [audit, review]\n")

    result = compose_effective_skillset(manifest, tmp_path)

    assert [s.name for s in result.skills] == ["audit", "review"]
