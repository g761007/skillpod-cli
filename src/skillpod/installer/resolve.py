"""Resolve a skill, falling back to the registry when no source matches.

Per `installer/spec.md` and `registry-discovery/spec.md`:

- Explicit `source:` on the skill → resolver only against that source,
  no registry fallback.
- Otherwise probe declared `sources[]` by priority; if none match, query
  the registry for a synthetic git source.
- When a lockfile entry pins the skill, the resolver SHALL pin to that
  commit so a subsequent integrity check can verify drift.
"""

from __future__ import annotations

from skillpod.lockfile.models import LockedSkill
from skillpod.manifest.models import SkillEntry, Skillfile, SourceEntry
from skillpod.registry import enforce
from skillpod.registry import lookup as registry_lookup
from skillpod.sources.errors import SourceNotFound
from skillpod.sources.git import resolve_git
from skillpod.sources.resolver import resolve_from_sources
from skillpod.sources.types import ResolvedSkill


def resolve_skill(
    skill: SkillEntry,
    manifest: Skillfile,
    *,
    locked: LockedSkill | None = None,
) -> ResolvedSkill:
    """Return a `ResolvedSkill` for `skill`, possibly via the registry."""

    # Frozen mode: pin to the lockfile commit and the lockfile URL.
    if locked is not None:
        # If the manifest declared the skill against an explicit local
        # source, the resolver should still go through the local path —
        # local sources have no lockfile entry, so the locked branch is
        # only reached for git-resolved skills.
        synthetic = SourceEntry(
            name=f"_locked:{skill.name}",
            type="git",
            url=locked.url,
            ref=locked.commit,
        )
        return resolve_git(skill.name, synthetic, explicit_commit=locked.commit)

    # Explicit source: no registry fallback.
    if skill.source is not None:
        return resolve_from_sources(skill, manifest.sources)

    # Try declared sources first; on miss, fall back to the registry.
    if manifest.sources:
        try:
            return resolve_from_sources(skill, manifest.sources)
        except SourceNotFound:
            pass

    info = registry_lookup(skill.name)
    enforce(manifest.registry.skills_sh, info)
    synthetic = SourceEntry(
        name=f"_registry:{skill.name}",
        type="git",
        url=info.url,
        ref=info.ref,
    )
    resolved = resolve_git(skill.name, synthetic, explicit_commit=info.commit)
    # Re-stamp source_kind so the caller can tell registry-derived
    # resolutions apart from manifest-declared git sources if it wants to.
    return ResolvedSkill(
        name=resolved.name,
        source_kind="registry",
        source_name=None,
        path=resolved.path,
        url=resolved.url,
        commit=resolved.commit,
    )


__all__ = ["resolve_skill"]
