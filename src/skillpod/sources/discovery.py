"""Walk a fetched source tree and enumerate the skills it contains.

A skill is a directory containing a top-level `SKILL.md`. Some sources
(`anthropics/skills`) hold many skills as immediate children; others
ship a single skill at the repo root. We support both shapes by:

1. If `<root>/SKILL.md` exists → treat `<root>` itself as one skill.
2. Otherwise scan up to depth 2 for any `<dir>/SKILL.md` and yield one
   `DiscoveredSkill` per match.

YAML frontmatter at the top of `SKILL.md` is parsed for the optional
`description:` field. Parse failures are non-fatal — the description
falls back to an empty string so listing never blows up on a single
malformed skill.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

_EXCLUDED_DIRS = frozenset({".git", "node_modules", "dist", "build", ".venv", "__pycache__"})
_MAX_DEPTH = 2


@dataclass(frozen=True)
class DiscoveredSkill:
    """One skill found inside a fetched source tree."""

    name: str
    description: str
    rel_path: str  # path relative to the discovery root (`.` for root-level)


def _read_frontmatter_description(skill_md: Path) -> str:
    """Best-effort extract of `description:` from a SKILL.md file."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    if not text.startswith("---"):
        return ""
    # Split on the closing `---` line.
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return ""
    body = parts[0][3:]  # drop leading "---"
    try:
        loaded = yaml.safe_load(body)
    except yaml.YAMLError:
        return ""
    if not isinstance(loaded, dict):
        return ""
    desc = loaded.get("description")
    if isinstance(desc, str):
        return desc.strip()
    return ""


def discover_skills(root: Path) -> list[DiscoveredSkill]:
    """Return every skill (directory containing SKILL.md) under `root`."""
    root = root.resolve()
    if not root.is_dir():
        return []

    found: list[DiscoveredSkill] = []
    seen_dirs: set[Path] = set()

    # Case 1: the root itself is a skill.
    root_skill_md = root / "SKILL.md"
    if root_skill_md.is_file():
        found.append(
            DiscoveredSkill(
                name=root.name,
                description=_read_frontmatter_description(root_skill_md),
                rel_path=".",
            )
        )
        seen_dirs.add(root)

    # Case 2: walk depth ≤ _MAX_DEPTH for nested skills.
    for skill_md in _walk_for_skill_md(root, depth=0):
        skill_dir = skill_md.parent
        if skill_dir in seen_dirs:
            continue
        seen_dirs.add(skill_dir)
        rel = skill_dir.relative_to(root)
        found.append(
            DiscoveredSkill(
                name=skill_dir.name,
                description=_read_frontmatter_description(skill_md),
                rel_path=str(rel),
            )
        )

    found.sort(key=lambda s: s.name)
    return found


def _walk_for_skill_md(directory: Path, *, depth: int) -> Iterator[Path]:
    if depth > _MAX_DEPTH:
        return
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError:
        return
    for entry in entries:
        if not entry.is_dir() or entry.name in _EXCLUDED_DIRS or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if skill_md.is_file():
            yield skill_md
            continue  # don't recurse into a discovered skill
        yield from _walk_for_skill_md(entry, depth=depth + 1)


__all__ = ["DiscoveredSkill", "discover_skills"]
