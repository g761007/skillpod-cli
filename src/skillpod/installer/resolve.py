"""Resolve a skill, falling back to the registry when no source matches.

Per `installer/spec.md` and `registry-discovery/spec.md`:

- Explicit `source:` on the skill → resolver only against that source,
  no registry fallback.
- Otherwise probe declared `sources[]` by priority; if none match, query
  the registry for a synthetic git source.

**Resolution follows the manifest, never an install record.** A record states
what happened last time; it does not constrain what may happen next. A project
that wants a fixed commit says so in ``skills[].version``, which
``resolve_from_sources`` passes through as ``explicit_commit`` — the pin lives
in the file a human wrote, not in generated state.

This replaces frozen mode, where a ``skillfile.lock`` entry was authoritative
and sticky: once locked, a skill resolved to that commit forever and upstream
was never consulted again.
"""

from __future__ import annotations

from skillpod.manifest.models import SkillEntry, Skillfile, SourceEntry
from skillpod.registry import enforce
from skillpod.registry import lookup as registry_lookup
from skillpod.sources.errors import SourceNotFound
from skillpod.sources.git import resolve_git
from skillpod.sources.resolver import resolve_from_sources
from skillpod.sources.types import ResolvedSkill


def resolve_skill(skill: SkillEntry, manifest: Skillfile) -> ResolvedSkill:
    """Return a `ResolvedSkill` for `skill`, possibly via the registry."""

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
        ref=resolved.ref,
    )


__all__ = ["resolve_skill"]
