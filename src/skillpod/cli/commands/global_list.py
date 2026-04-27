"""`skillpod global list` — enumerate advisory global skill directories."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from skillpod.cli._output import emit

GLOBAL_SKILL_DIRS: tuple[tuple[str, str], ...] = (
    ("claude", ".claude/skills"),
    ("codex", ".codex/skills"),
    ("gemini", ".gemini/skills"),
    ("cursor", ".cursor/skills"),
    ("opencode", ".opencode/skills"),
    ("antigravity", ".antigravity/skills"),
)


class GlobalSkill(TypedDict):
    agent: str
    name: str
    path: str
    size_bytes: int
    mtime: str


def known_global_roots(home: Path | None = None) -> list[tuple[str, Path]]:
    root = (home or Path.home()).expanduser()
    return [(agent, root / rel) for agent, rel in GLOBAL_SKILL_DIRS]


def directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def scan_global_skills(home: Path | None = None) -> list[GlobalSkill]:
    rows: list[GlobalSkill] = []
    for agent, root in known_global_roots(home):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            stat = child.stat()
            rows.append(
                GlobalSkill(
                    agent=agent,
                    name=child.name,
                    path=str(child),
                    size_bytes=directory_size(child),
                    mtime=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                )
            )
    return rows


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    rows = scan_global_skills()
    if json_output:
        emit(rows, json_output=True)
        return

    if not rows:
        emit(rows, json_output=False, human="No global skills found.")
        return

    name_w = max(4, *(len(row["name"]) for row in rows))
    agent_w = max(5, *(len(row["agent"]) for row in rows))
    lines = [f"{'AGENT':<{agent_w}}  {'NAME':<{name_w}}  SIZE  MTIME  PATH"]
    for row in rows:
        lines.append(
            f"{row['agent']:<{agent_w}}  {row['name']:<{name_w}}  "
            f"{row['size_bytes']}  {row['mtime']}  {row['path']}"
        )
    emit(rows, json_output=False, human="\n".join(lines))


__all__ = [
    "GLOBAL_SKILL_DIRS",
    "GlobalSkill",
    "directory_size",
    "known_global_roots",
    "run",
    "scan_global_skills",
]
