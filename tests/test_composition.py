"""Tests for parse_profile_expr and compose_effective_skillset multi-profile path."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from skillpod.manifest.loader import loads
from skillpod.profile.errors import ProfileError
from skillpod.skillset.compose import compose_effective_skillset, parse_profile_expr


def _manifest(text: str):  # type: ignore[return]
    return loads(text)


# ---- parse_profile_expr -------------------------------------------------------


def test_parse_profile_expr_single() -> None:
    assert parse_profile_expr("dev") == ["dev"]


def test_parse_profile_expr_two() -> None:
    assert parse_profile_expr("dev+reviewer") == ["dev", "reviewer"]


def test_parse_profile_expr_strips_spaces() -> None:
    assert parse_profile_expr("dev + reviewer") == ["dev", "reviewer"]


# ---- _compose_multi via compose_effective_skillset ----------------------------


def test_compose_multi_union_skills(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit, lint]\n"
        "  reviewer:\n"
        "    skills: [audit, review]\n"
    )

    result = compose_effective_skillset(manifest, tmp_path, profile_name="dev+reviewer")

    skill_names = [s.name for s in result.skills]
    # Union: audit, lint, review (deduped, left-to-right order from each profile)
    assert set(skill_names) == {"audit", "lint", "review"}


def test_compose_multi_order_stable(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review, lint]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit, lint]\n"
        "  reviewer:\n"
        "    skills: [review]\n"
    )

    result_ab = compose_effective_skillset(manifest, tmp_path, profile_name="dev+reviewer")
    result_ba = compose_effective_skillset(manifest, tmp_path, profile_name="reviewer+dev")

    # Both should contain the same set of skills
    names_ab = {s.name for s in result_ab.skills}
    names_ba = {s.name for s in result_ba.skills}
    assert names_ab == names_ba


def test_compose_multi_unknown_profile_raises(tmp_path: Path) -> None:
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit]\n"
    )

    with pytest.raises(ProfileError):
        compose_effective_skillset(manifest, tmp_path, profile_name="dev+nonexistent")


def test_composition_emits_no_experimental_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Composition is stable as of v0.7.0 — no experimental stderr warning."""
    manifest = _manifest(
        "version: 1\n"
        "skills: [audit, review]\n"
        "profiles:\n"
        "  dev:\n"
        "    skills: [audit]\n"
        "  reviewer:\n"
        "    skills: [review]\n"
    )

    buf = io.StringIO()
    monkeypatch.setattr("sys.stderr", buf)

    compose_effective_skillset(manifest, tmp_path, profile_name="dev+reviewer")

    assert "experimental" not in buf.getvalue()
