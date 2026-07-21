"""Attach or detach a skill from a project's agents, without re-downloading.

The project-scope counterpart to `global link` / `global unlink`. Both scopes
answer the same question — *should this agent see this skill?* — and neither
touches the network: the materialised copy under `.skillpod/skills/` is the
source, and unlinking leaves it in place so re-linking is instant.

`link` also covers the case where the skill is not in the project yet but the
user already has it globally: the copy is taken from `~/.skillpod/skills/`
rather than fetched again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_registry import get_adapter
from skillpod.installer.errors import InstallUserError
from skillpod.installer.fanout import (
    materialise_fanout,
    materialise_install_root,
    rollback_on_failure,
)
from skillpod.installer.paths import (
    agent_skill_dir,
    global_skill_dir,
    is_managed_fanout,
    project_skill_dir,
)
from skillpod.manifest.models import Skillfile


@dataclass
class LinkReport:
    name: str
    linked: list[str] = field(default_factory=list)
    already_linked: list[str] = field(default_factory=list)
    copied_from_global: bool = False


@dataclass
class UnlinkReport:
    name: str
    unlinked: list[str] = field(default_factory=list)
    not_linked: list[str] = field(default_factory=list)
    skipped_unmanaged: list[str] = field(default_factory=list)


def _target_agents(manifest: Skillfile, agents: list[str] | None) -> list[str]:
    declared = [a.name for a in manifest.agents]
    if agents is None:
        return declared
    unknown = sorted(set(agents) - set(declared))
    if unknown:
        raise InstallUserError(
            f"agent(s) not declared in the manifest: {', '.join(unknown)}; "
            f"declared: {', '.join(declared) or '(none)'}"
        )
    return [a for a in declared if a in set(agents)]


def link_skill(
    project_root: Path,
    manifest: Skillfile,
    skill_name: str,
    *,
    agents: list[str] | None = None,
    home: Path | None = None,
) -> LinkReport:
    """Fan `skill_name` out to the project's agents.

    Raises ``InstallUserError`` when the skill is nowhere to be found, since
    linking cannot invent content — `skillpod add` is what fetches it.
    """
    targets = _target_agents(manifest, agents)
    report = LinkReport(name=skill_name)
    skill_dir = project_skill_dir(project_root, skill_name)

    with rollback_on_failure() as rollback:
        if not skill_dir.exists():
            source = global_skill_dir(skill_name, home)
            if not source.is_dir():
                raise InstallUserError(
                    f"skill {skill_name!r} is not installed in this project or "
                    f"globally — run `skillpod add` to fetch it first"
                )
            # Already on the machine: copy rather than fetch.
            materialise_install_root(
                skill_dir, source, skill_name=skill_name, record=rollback
            )
            report.copied_from_global = True

        mode = InstallMode(manifest.install.mode)
        fallback = [str(f) for f in manifest.install.fallback]
        for agent in targets:
            target = agent_skill_dir(project_root, agent, skill_name)
            if is_managed_fanout(target, project_root):
                report.already_linked.append(agent)
                continue
            materialise_fanout(
                skill_name=skill_name,
                source_dir=skill_dir,
                target_dir=target,
                agent=agent,
                project_root=project_root,
                mode=mode,
                fallback=fallback,
                adapter=get_adapter(agent),
                record=rollback,
            )
            report.linked.append(agent)

    return report


def unlink_skill(
    project_root: Path,
    manifest: Skillfile,
    skill_name: str,
    *,
    agents: list[str] | None = None,
) -> UnlinkReport:
    """Detach `skill_name` from the project's agents, keeping the copy.

    Only skillpod-created fan-out is removed. Anything the user put there by
    hand is reported and left alone — deleting it would be destroying work
    skillpod does not own.
    """
    targets = _target_agents(manifest, agents)
    report = UnlinkReport(name=skill_name)

    for agent in targets:
        target = agent_skill_dir(project_root, agent, skill_name)
        if is_managed_fanout(target, project_root):
            target.unlink()
            report.unlinked.append(agent)
        elif target.exists() or target.is_symlink():
            report.skipped_unmanaged.append(agent)
        else:
            report.not_linked.append(agent)

    return report


__all__ = ["LinkReport", "UnlinkReport", "link_skill", "unlink_skill"]
