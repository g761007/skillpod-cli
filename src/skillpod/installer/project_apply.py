"""Make a project's fan-out match the active profile.

Until now a project-scope `switch` only wrote a pointer: `resolve` and `status`
honoured the profile, but `.<agent>/skills/` never changed, so the agent went
on loading every skill. A profile the agent cannot observe is decorative.

This reconciles the two, mirroring `global_apply.plan_apply`:

- **Fan-out only.** `.skillpod/skills/` keeps the full declared set, so
  switching profiles is instant and offline — an excluded skill is unlinked,
  never deleted, and comes straight back.
- **Managed entries only.** Anything the user placed by hand is left alone.
- **A skill satisfied by the global layer is not the project's to manage**, so
  it never appears in either list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.paths import (
    agent_skill_dir,
    install_root,
    is_managed_fanout,
)
from skillpod.manifest.models import Skillfile
from skillpod.skillset.compose import compose_effective_skillset


@dataclass
class FanoutPlan:
    """The difference between what the agents see and what the profile wants."""

    profile: str | None
    to_link: list[str] = field(default_factory=list)
    to_unlink: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.to_link or self.to_unlink)


def plan_project_fanout(
    project_root: Path,
    manifest: Skillfile,
    *,
    profile_name: str | None = None,
    home: Path | None = None,
) -> FanoutPlan:
    """Work out which fan-out entries to add or remove. Touches nothing."""
    effective = compose_effective_skillset(
        manifest, project_root, profile_name=profile_name, home=home
    )
    wanted = {s.name for s in effective.skills}

    agents = [a.name for a in manifest.agents]
    skills_root = install_root(project_root)
    materialised = (
        {d.name for d in skills_root.iterdir() if d.is_dir()}
        if skills_root.is_dir()
        else set()
    )

    plan = FanoutPlan(profile=profile_name)
    for name in sorted(materialised):
        linked_anywhere = any(
            is_managed_fanout(agent_skill_dir(project_root, agent, name), project_root)
            for agent in agents
        )
        fully_linked = agents and all(
            is_managed_fanout(agent_skill_dir(project_root, agent, name), project_root)
            for agent in agents
        )
        if name in wanted:
            if not fully_linked:
                plan.to_link.append(name)
        elif linked_anywhere:
            plan.to_unlink.append(name)

    return plan


def execute_project_fanout(
    project_root: Path, manifest: Skillfile, plan: FanoutPlan
) -> FanoutPlan:
    """Apply `plan`. Returns it unchanged, for symmetry with the global side."""
    # Imported here rather than at module scope: project_link imports the
    # adapter registry, which the pipeline sets up, and this module is reached
    # from both.
    from skillpod.installer.project_link import link_skill, unlink_skill

    for name in plan.to_link:
        link_skill(project_root, manifest, name)
    for name in plan.to_unlink:
        unlink_skill(project_root, manifest, name)
    return plan


__all__ = ["FanoutPlan", "execute_project_fanout", "plan_project_fanout"]
