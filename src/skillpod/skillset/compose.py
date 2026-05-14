"""Compose the effective skill set from manifest, user_skills, and an optional profile."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

from skillpod.installer.expand import flatten
from skillpod.installer.user_skills import discover_user_skills
from skillpod.manifest.models import SkillEntry, Skillfile
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import get_project_profile, load_global_profile
from skillpod.skillset.layers import LayerOrigin


@dataclass(frozen=True)
class EffectiveSkillset:
    """The resolved set of skills and their layer provenance."""

    skills: list[SkillEntry]
    provenance: dict[str, LayerOrigin]


def compose_effective_skillset(
    manifest: Skillfile,
    project_root: Path,
    *,
    profile_name: str | None = None,
    home: Path | None = None,
) -> EffectiveSkillset:
    """Return the effective skill list after applying manifest, user_skills, and profile.

    When `profile_name` is None, the full combined set is returned (same
    behaviour as pre-v0.6.0 pipeline).  When given, the profile is resolved
    from project profiles first, then global profiles; a ProfileError is
    raised if it cannot be found or if it references unknown skills.
    """
    flat_skills = flatten(manifest)
    user_skills: dict[str, Path] = discover_user_skills(project_root)

    flat_names = {s.name for s in flat_skills}
    shadowed = sorted(flat_names & set(user_skills))
    if shadowed:
        warnings.warn(
            ".skillpod/user_skills entries shadow manifest skill(s): "
            + ", ".join(shadowed),
            UserWarning,
            stacklevel=2,
        )

    combined: list[SkillEntry] = list(flat_skills)
    for name in user_skills:
        if name not in flat_names:
            combined.append(SkillEntry(name=name))

    if profile_name is None:
        user_skill_names = set(user_skills)
        provenance = {
            s.name: (
                LayerOrigin.USER_SKILL if s.name in user_skill_names else LayerOrigin.PROJECT
            )
            for s in combined
        }
        return EffectiveSkillset(skills=combined, provenance=provenance)

    # Resolve profile: project first, then global.
    profile = get_project_profile(manifest, profile_name)
    if profile is None:
        profile = load_global_profile(profile_name, home)
    if profile is None:
        raise ProfileError(
            f"profile '{profile_name}' not found in project or global profiles"
        )

    combined_names = {s.name for s in combined}
    unknown = [s for s in profile.skills if s not in combined_names]
    if unknown:
        raise ProfileError(
            f"profile '{profile_name}': unknown skill(s): "
            + ", ".join(repr(s) for s in unknown)
            + f"; available: {sorted(combined_names) or '<none>'}"
        )

    profile_skill_set = set(profile.skills)
    filtered = [s for s in combined if s.name in profile_skill_set]
    provenance = {s.name: LayerOrigin.PROFILE_FILTER for s in filtered}
    return EffectiveSkillset(skills=filtered, provenance=provenance)


__all__ = ["EffectiveSkillset", "compose_effective_skillset"]
