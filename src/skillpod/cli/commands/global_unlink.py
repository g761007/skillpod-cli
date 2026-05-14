"""`skillpod global unlink` — remove agent fan-out symlinks for a globally installed skill."""

from __future__ import annotations

import os
from pathlib import Path

from skillpod.cli._output import emit
from skillpod.installer.global_install import DEFAULT_GLOBAL_AGENTS
from skillpod.installer.paths import global_agent_skill_dir, is_managed_global_fanout


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    agents: list[str] | None,
    json_output: bool,
) -> None:
    target_agents = agents if agents is not None else list(DEFAULT_GLOBAL_AGENTS)

    unlinked: list[str] = []
    skipped_unmanaged: list[str] = []
    missing: list[str] = []

    for agent in target_agents:
        link_path = global_agent_skill_dir(agent, skill_name)
        if not link_path.exists() and not link_path.is_symlink():
            missing.append(agent)
            continue
        if is_managed_global_fanout(link_path, skill_name):
            link_path.unlink()
            unlinked.append(agent)
        else:
            skipped_unmanaged.append(str(link_path))

    payload: dict[str, object] = {
        "ok": True,
        "name": skill_name,
        "unlinked": unlinked,
        "skipped_unmanaged": skipped_unmanaged,
        "missing": missing,
    }

    if json_output:
        emit(payload, json_output=True)
        return

    lines: list[str] = []
    for agent in unlinked:
        lines.append(f"Unlinked: {global_agent_skill_dir(agent, skill_name)}")
    for path_str in skipped_unmanaged:
        link = Path(path_str)
        if link.is_symlink():
            try:
                target = os.readlink(link)
            except OSError:
                target = "?"
            lines.append(f"Skipped (not managed): {link} -> {target}")
        else:
            lines.append(f"Skipped (not managed): {link}")
    if not lines and not missing:
        lines.append(f"Nothing to do for {skill_name!r}.")
    emit(payload, json_output=False, human="\n".join(lines) if lines else "")


__all__ = ["run"]
