"""Expand manifest groups into the effective flat skill set."""

from __future__ import annotations

from skillpod.manifest.models import SkillEntry, Skillfile


def flatten(manifest: Skillfile) -> list[SkillEntry]:
    """Return manifest skills plus selected group members, deduplicated by name.

    Entries are considered in manifest order: top-level ``skills`` first, then
    each group listed in ``use``. The first occurrence fixes display/install
    order. Later duplicates are ignored unless the later entry declares an
    explicit ``source:``, in which case it replaces the existing entry.
    """

    ordered: list[SkillEntry] = []
    positions: dict[str, int] = {}

    def add(entry: SkillEntry) -> None:
        pos = positions.get(entry.name)
        if pos is None:
            positions[entry.name] = len(ordered)
            ordered.append(entry)
            return
        if entry.source is not None:
            ordered[pos] = entry

    for skill in manifest.skills:
        add(skill)
    for group_name in manifest.use:
        for skill in manifest.groups[group_name]:
            add(skill)

    return ordered


__all__ = ["flatten"]
