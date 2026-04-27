"""Result types returned by the source resolver."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ResolvedSkill:
    """The outcome of resolving a single skill against a single source.

    Attributes
    ----------
    name:
        The skill name as it appears in the manifest.
    source_kind:
        Which kind of source produced this — `local`, `git`, or `registry`
        (registry-derived results land as synthetic `git` resolutions in
        practice, but we keep the distinction in the result so the
        installer can decide whether to write a lockfile entry).
    source_name:
        The matching `sources[].name` when applicable, else `None` for
        registry-resolved skills.
    path:
        Absolute path to the materialised skill directory (cache for git,
        the configured path for local).
    url:
        The git URL associated with the resolution, or `None` for `local`.
    commit:
        The 40-character SHA the skill is pinned to, or `None` for `local`.
    """

    name: str
    source_kind: Literal["local", "git", "registry"]
    source_name: str | None
    path: Path
    url: str | None
    commit: str | None


__all__ = ["ResolvedSkill"]
