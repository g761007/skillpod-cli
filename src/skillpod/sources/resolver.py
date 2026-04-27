"""Top-level skill resolver — priority probe + explicit-source override.

Priority semantics (per `source-resolver/spec.md`):

- A `SkillEntry` declaring an explicit ``source:`` is resolved against
  that source only; lower-priority sources are not probed.
- Otherwise, sources are probed in descending ``priority`` order and the
  first source that yields the skill wins.
- The registry fallback lives in `skillpod.installer` (because it has
  side-effects on lockfile decisions) and is not part of this module.
"""

from __future__ import annotations

from skillpod.manifest.models import SkillEntry, SourceEntry
from skillpod.sources.errors import SourceError, SourceNotFound
from skillpod.sources.git import resolve_git
from skillpod.sources.local import resolve_local
from skillpod.sources.types import ResolvedSkill


def _resolve_one(skill: SkillEntry, source: SourceEntry) -> ResolvedSkill:
    if source.type == "local":
        return resolve_local(skill.name, source)
    if source.type == "git":
        return resolve_git(skill.name, source, explicit_commit=skill.version)
    raise SourceError(f"unsupported source type {source.type!r}")


def resolve_from_sources(
    skill: SkillEntry,
    sources: list[SourceEntry],
) -> ResolvedSkill:
    """Resolve ``skill`` using the manifest's declared sources.

    Raises `SourceNotFound` when no declared source can satisfy the skill.
    Callers may then fall back to the registry.
    """
    by_name = {s.name: s for s in sources}

    if skill.source is not None:
        if skill.source not in by_name:
            raise SourceError(
                f"skill {skill.name!r}: explicit source {skill.source!r} not declared"
            )
        return _resolve_one(skill, by_name[skill.source])

    ordered = sorted(sources, key=lambda s: s.priority, reverse=True)
    last_error: Exception | None = None
    for src in ordered:
        try:
            return _resolve_one(skill, src)
        except SourceNotFound as exc:
            last_error = exc
            continue

    raise SourceNotFound(
        f"no declared source provides skill {skill.name!r}"
        + (f" (last error: {last_error})" if last_error else "")
    )


__all__ = ["resolve_from_sources"]
