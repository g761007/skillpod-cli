"""`skillpod global link` — fan-out an existing ~/.skillpod/skills/<name> to agent dirs."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail
from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.installer.errors import InstallConflict, InstallSystemError
from skillpod.installer.global_install import DEFAULT_GLOBAL_AGENTS, materialise_agent_link
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_skill_dir,
    is_managed_global_fanout,
)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    agents: list[str] | None,
    yes: bool,
    json_output: bool,
) -> None:
    install_root = global_skill_dir(skill_name)
    if not install_root.is_dir():
        raise fail(
            f"skill {skill_name!r} is not installed globally "
            f"(expected {install_root}); run 'skillpod add --global' first",
            code=1,
            json_output=json_output,
        )

    target_agents = agents if agents is not None else list(DEFAULT_GLOBAL_AGENTS)
    adapter = IdentityAdapter()

    linked: list[str] = []
    already_linked: list[str] = []
    failed: list[dict[str, str]] = []

    for agent in target_agents:
        link_path = global_agent_skill_dir(agent, skill_name)
        if is_managed_global_fanout(link_path, skill_name):
            already_linked.append(agent)
            continue
        link_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            materialise_agent_link(link_path, install_root, adapter, InstallMode.SYMLINK, force=yes)
            linked.append(agent)
        except InstallConflict as exc:
            failed.append({"agent": agent, "reason": str(exc)})
        except InstallSystemError as exc:
            failed.append({"agent": agent, "reason": str(exc)})

    ok = not failed
    payload: dict[str, object] = {
        "ok": ok,
        "name": skill_name,
        "linked": linked,
        "already_linked": already_linked,
        "failed": failed,
    }

    if json_output:
        emit(payload, json_output=True)
    else:
        lines: list[str] = []
        for agent in linked:
            lines.append(f"Linked: {agent} -> {install_root}")
        for agent in already_linked:
            lines.append(f"Already linked: {agent}")
        for item in failed:
            lines.append(f"Failed {item['agent']}: {item['reason']}")
        if not lines:
            lines.append(f"Nothing to do for {skill_name!r}.")
        emit(payload, json_output=False, human="\n".join(lines))

    if not ok:
        raise SystemExit(1)


__all__ = ["run"]
