"""Resolve a `local` source — a path on the user's machine."""

from __future__ import annotations

from pathlib import Path

from skillpod.manifest.models import SourceEntry
from skillpod.sources.errors import SourceError, SourceNotFound
from skillpod.sources.types import ResolvedSkill


def resolve_local(skill_name: str, source: SourceEntry) -> ResolvedSkill:
    """Return the absolute path of ``<source.path>/<skill_name>`` if it exists."""
    if source.type != "local":
        raise SourceError(f"resolve_local called for non-local source {source.name!r}")
    if not source.path:
        raise SourceError(f"local source {source.name!r} is missing `path:`")

    root = Path(source.path).expanduser()
    skill_dir = root / skill_name
    if not skill_dir.exists():
        raise SourceNotFound(
            f"local source {source.name!r}: no skill named {skill_name!r} under {root}"
        )
    if not skill_dir.is_dir():
        raise SourceError(
            f"local source {source.name!r}: {skill_dir} exists but is not a directory"
        )

    return ResolvedSkill(
        name=skill_name,
        source_kind="local",
        source_name=source.name,
        path=skill_dir.resolve(),
        url=None,
        commit=None,
    )


__all__ = ["resolve_local"]
