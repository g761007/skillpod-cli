"""`skillpod global list` — enumerate global skill directories."""

from __future__ import annotations

import shutil
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from skillpod.cli._output import emit
from skillpod.installer.global_install import DEFAULT_GLOBAL_AGENTS
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_install_root,
    is_managed_global_fanout,
)

GLOBAL_SKILL_DIRS: tuple[tuple[str, str], ...] = (
    ("claude", ".claude/skills"),
    ("codex", ".codex/skills"),
    ("gemini", ".gemini/skills"),
    ("cursor", ".cursor/skills"),
    ("opencode", ".opencode/skills"),
    ("antigravity", ".antigravity/skills"),
)

_AGENT_ABBREV: dict[str, str] = {
    "claude": "cl",
    "codex": "cx",
    "gemini": "ge",
    "cursor": "cu",
    "opencode": "oc",
    "antigravity": "ag",
}


def _format_linked(linked: list[str]) -> str:
    """Compact representation of linked agents for human-readable output."""
    if not linked:
        return "-"
    if set(linked) >= set(DEFAULT_GLOBAL_AGENTS):
        return "all"
    return ",".join(_AGENT_ABBREV.get(a, a) for a in linked)


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def _read_description(skill_dir: Path) -> str | None:
    """Extract `description:` from SKILL.md YAML frontmatter, or None."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        in_front = False
        for line in skill_md.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() == "---":
                in_front = not in_front
                continue
            if in_front and line.startswith("description:"):
                return line[len("description:"):].strip()
    except OSError:
        pass
    return None


def _format_agents_visual(linked: list[str]) -> str:
    """Show ●/○ indicator per agent with full name."""
    linked_set = set(linked)
    parts = [
        f"● {agent}" if agent in linked_set else f"○ {agent}"
        for agent in DEFAULT_GLOBAL_AGENTS
    ]
    return "  ".join(parts)


def _box_line(content: str, width: int) -> str:
    """Pad `content` to fill a box interior line of total `width` chars."""
    inner = width - 4  # │ + space + ... + space + │
    return f"│ {content:<{inner}} │"


def _render_box(name: str, body_lines: list[str], width: int) -> str:
    """Render a titled box with Unicode border characters."""
    inner = width - 4
    fill_len = width - len(name) - 5  # ┌─ {name} {fill}┐
    top = f"┌─ {name} {'─' * max(0, fill_len)}┐"
    bottom = "└" + "─" * (width - 2) + "┘"
    rows = [top]
    for line in body_lines:
        # wrap long lines to inner width
        if len(line) > inner:
            for chunk in textwrap.wrap(line, inner) or [""]:
                rows.append(_box_line(chunk, width))
        else:
            rows.append(_box_line(line, width))
    rows.append(bottom)
    return "\n".join(rows)


class GlobalSkill(TypedDict):
    agent: str
    name: str
    path: str
    size_bytes: int
    mtime: str


class InstallRootSkill(TypedDict):
    name: str
    path: str
    size_bytes: int
    mtime: str
    linked: list[str]


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
    """Per-agent scan: list skills found under each ``~/.<agent>/skills/``."""
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


def scan_install_root_skills(home: Path | None = None) -> list[InstallRootSkill]:
    """Install-root scan: list skills under ``~/.skillpod/skills/`` with linked agents."""
    root = global_install_root(home)
    if not root.is_dir():
        return []
    rows: list[InstallRootSkill] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        stat = child.stat()
        linked = [
            agent
            for agent in DEFAULT_GLOBAL_AGENTS
            if is_managed_global_fanout(
                global_agent_skill_dir(agent, child.name, home), child.name, home
            )
        ]
        rows.append(
            InstallRootSkill(
                name=child.name,
                path=str(child),
                size_bytes=directory_size(child),
                mtime=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                linked=linked,
            )
        )
    return rows


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    agents_view: bool = False,
    verbose: bool = False,
) -> None:
    if agents_view:
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
        return

    root_rows = scan_install_root_skills()
    if json_output:
        emit(root_rows, json_output=True)
        return
    if not root_rows:
        emit(root_rows, json_output=False, human="No skills installed in ~/.skillpod/skills/.")
        return

    if verbose:
        home = Path.home()
        term_w = min(shutil.get_terminal_size((80, 24)).columns, 100)
        box_w = max(60, term_w - 2)
        blocks: list[str] = []
        for r in root_rows:
            skill_path = Path(r["path"])
            desc = _read_description(skill_path)
            agents_line = _format_agents_visual(r["linked"])
            try:
                display_path = "~/" + str(skill_path.relative_to(home))
            except ValueError:
                display_path = str(skill_path)
            meta = f"{_human_size(r['size_bytes'])}  ·  {r['mtime'][:10]}  ·  {display_path}"
            body: list[str] = []
            if desc:
                body.append(desc)
                body.append("")
            body.append(agents_line)
            body.append("")
            body.append(meta)
            blocks.append(_render_box(r["name"], body, box_w))
        emit(root_rows, json_output=False, human="\n".join(blocks))
        return

    name_w = max(4, *(len(r["name"]) for r in root_rows))
    linked_w = max(6, *(len(_format_linked(r["linked"])) for r in root_rows))
    size_w = max(4, *(len(str(r["size_bytes"])) for r in root_rows))
    lines = [f"{'NAME':<{name_w}}  {'LINKED':<{linked_w}}  {'SIZE':>{size_w}}  MTIME"]
    for r in root_rows:
        linked_str = _format_linked(r["linked"])
        date_str = r["mtime"][:10]
        lines.append(
            f"{r['name']:<{name_w}}  {linked_str:<{linked_w}}  {r['size_bytes']:>{size_w}}  {date_str}"
        )
    emit(root_rows, json_output=False, human="\n".join(lines))


__all__ = [
    "GLOBAL_SKILL_DIRS",
    "GlobalSkill",
    "InstallRootSkill",
    "directory_size",
    "known_global_roots",
    "run",
    "scan_global_skills",
    "scan_install_root_skills",
]
