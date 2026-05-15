"""Compose the effective skill set from manifest, user_skills, and an optional profile."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.expand import flatten
from skillpod.installer.user_skills import discover_user_skills
from skillpod.manifest.models import ActivationPolicy, ProfileEntry, SkillEntry, Skillfile
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import get_project_profile, load_global_profile
from skillpod.skillset.layers import LayerOrigin


@dataclass(frozen=True)
class EffectiveSkillset:
    """The resolved set of skills and their layer provenance."""

    skills: list[SkillEntry]
    provenance: dict[str, LayerOrigin]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _apply_activation_policy(
    activation: ActivationPolicy,
    *,
    profile_name: str | None,
    ignore_global: bool,
    manifest: Skillfile,
    home: Path | None,
) -> tuple[ProfileEntry | None, set[str], tuple[str, ...]]:
    """Resolve the activation policy to an effective profile.

    Returns (effective_profile, global_skill_names, warnings).
    - ``effective_profile``: the merged/selected ProfileEntry, or None for base-only.
    - ``global_skill_names``: skill names that came exclusively from a global profile
      (used to assign GLOBAL_PROFILE_FILTER provenance).
    - ``warnings``: non-fatal informational messages for the CLI to print to stderr.

    Raises ProfileError for unresolvable or policy-violating requests.
    """
    # Determine effective profile name (manual mode ignores default_profile)
    if activation.mode == "manual":
        name = profile_name
    else:
        name = profile_name or activation.default_profile

    if name is None:
        return (None, set(), ())

    # Global profiles are off when: strict mode, inherit_global=False, or --ignore-global
    can_use_global = (
        activation.mode != "strict"
        and activation.inherit_global
        and not ignore_global
    )

    project_p = get_project_profile(manifest, name)
    global_p: ProfileEntry | None = load_global_profile(name, home) if can_use_global else None

    if activation.mode == "strict":
        if project_p is not None:
            return (project_p, set(), ())
        # Warn if a global profile exists but was blocked by strict policy
        if activation.inherit_global and not ignore_global:
            blocked = load_global_profile(name, home)
            if blocked is not None:
                warnings.warn(
                    f"global profile '{name}' was rejected: "
                    "strict activation policy only accepts project profiles",
                    UserWarning,
                    stacklevel=4,
                )
        raise ProfileError(
            f"profile '{name}' not found in project profiles "
            "(strict mode: only project profiles are accepted)"
        )

    if activation.mode == "merge":
        if project_p is None and global_p is None:
            raise ProfileError(
                f"profile '{name}' not found in project or global profiles"
            )
        # Union: project skills first, then global-only skills
        merged_skills: list[str] = list(project_p.skills) if project_p else []
        project_skill_set = set(merged_skills)
        global_only_names: set[str] = set()
        if global_p is not None:
            for skill in global_p.skills:
                if skill not in project_skill_set:
                    merged_skills.append(skill)
                    global_only_names.add(skill)
        merged_agents = list(
            dict.fromkeys(
                (project_p.agents if project_p else [])
                + (global_p.agents if global_p else [])
            )
        )
        merged_profile = ProfileEntry(
            type=project_p.type if project_p else (global_p.type if global_p else None),
            agents=merged_agents,
            skills=merged_skills,
        )
        return (merged_profile, global_only_names, ())

    if activation.mode == "fallback":
        if project_p is not None:
            return (project_p, set(), ())
        if global_p is not None:
            return (
                global_p,
                set(global_p.skills),
                (f"no project profile '{name}'; using global profile as fallback",),
            )
        raise ProfileError(
            f"profile '{name}' not found in project or global profiles"
        )

    # manual mode: project first, then global (v0.6.0 behaviour)
    if project_p is not None:
        return (project_p, set(), ())
    if global_p is not None:
        return (global_p, set(global_p.skills), ())
    raise ProfileError(
        f"profile '{name}' not found in project or global profiles"
    )


def compose_effective_skillset(
    manifest: Skillfile,
    project_root: Path,
    *,
    profile_name: str | None = None,
    home: Path | None = None,
    ignore_global: bool = False,
) -> EffectiveSkillset:
    """Return the effective skill list after applying manifest, user_skills, and profile.

    When no profile is active (no ``--profile`` flag and no ``default_profile``
    in the activation policy), the full combined set is returned, matching
    pre-v0.6.0 pipeline behaviour.  The ``ignore_global`` flag forces all
    global profiles to be skipped, overriding ``activation.inherit_global``.
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

    effective_profile, global_skill_names, policy_warnings = _apply_activation_policy(
        manifest.activation,
        profile_name=profile_name,
        ignore_global=ignore_global,
        manifest=manifest,
        home=home,
    )

    if effective_profile is None:
        user_skill_names = set(user_skills)
        provenance = {
            s.name: (
                LayerOrigin.USER_SKILL if s.name in user_skill_names else LayerOrigin.PROJECT
            )
            for s in combined
        }
        return EffectiveSkillset(
            skills=combined, provenance=provenance, warnings=policy_warnings
        )

    combined_names = {s.name for s in combined}
    unknown = [s for s in effective_profile.skills if s not in combined_names]
    if unknown:
        effective_name = profile_name or manifest.activation.default_profile or "unknown"
        raise ProfileError(
            f"profile '{effective_name}': unknown skill(s): "
            + ", ".join(repr(s) for s in unknown)
            + f"; available: {sorted(combined_names) or '<none>'}"
        )

    profile_skill_set = set(effective_profile.skills)
    filtered = [s for s in combined if s.name in profile_skill_set]
    provenance = {
        s.name: (
            LayerOrigin.GLOBAL_PROFILE_FILTER
            if s.name in global_skill_names
            else LayerOrigin.PROFILE_FILTER
        )
        for s in filtered
    }
    return EffectiveSkillset(
        skills=filtered, provenance=provenance, warnings=policy_warnings
    )


__all__ = ["EffectiveSkillset", "compose_effective_skillset"]
