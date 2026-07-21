"""Where each recommended skill actually lives, and whether it is usable.

One answer, shared. `list`, `status`, and anything else that wants to say
"you have this / you don't" ask here rather than each re-deriving it from the
filesystem — three copies of that logic would drift, and the disagreement
would surface as two commands contradicting each other about the same skill.

`doctor` deliberately keeps its own checks: it reports *faults* with codes and
paths, which is a different question from *which layer provides this*.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from skillpod.installer.expand import flatten
from skillpod.installer.paths import (
    agent_skill_dir,
    global_skill_dir,
    install_root,
    is_managed_fanout,
    project_record_path,
)
from skillpod.installer.user_skills import discover_user_skills
from skillpod.manifest.models import Skillfile
from skillpod.record import io as record_io


class SkillState(StrEnum):
    """Which layer satisfies a recommended skill, if any."""

    PROJECT = "project"
    """Materialised under `.skillpod/skills/`."""

    GLOBAL = "global"
    """Not here, but provided by `~/.skillpod/skills/`."""

    USER = "user"
    """Supplied by hand under `.skillpod/user_skills/`."""

    MISSING = "missing"
    """Recommended and not present anywhere — `skillpod install` fixes it."""

    BROKEN = "broken"
    """Present but unusable: the record and the disk disagree, or an agent's
    fan-out is missing or points somewhere unmanaged."""


SATISFIED = (SkillState.PROJECT, SkillState.GLOBAL, SkillState.USER)


@dataclass(frozen=True)
class SkillStatus:
    name: str
    state: SkillState
    detail: str | None = None

    @property
    def satisfied(self) -> bool:
        return self.state in SATISFIED


@dataclass(frozen=True)
class Inventory:
    skills: list[SkillStatus]

    def _count(self, *states: SkillState) -> int:
        return sum(1 for s in self.skills if s.state in states)

    @property
    def recommended(self) -> int:
        return len(self.skills)

    @property
    def satisfied(self) -> int:
        return self._count(*SATISFIED)

    @property
    def from_global(self) -> int:
        return self._count(SkillState.GLOBAL)

    @property
    def from_project(self) -> int:
        return self._count(SkillState.PROJECT)

    @property
    def from_user(self) -> int:
        return self._count(SkillState.USER)

    @property
    def missing(self) -> list[str]:
        return [s.name for s in self.skills if s.state is SkillState.MISSING]

    @property
    def broken(self) -> list[str]:
        return [s.name for s in self.skills if s.state is SkillState.BROKEN]


def take_inventory(
    manifest: Skillfile, project_root: Path, *, home: Path | None = None
) -> Inventory:
    """Classify every skill the manifest recommends, plus any user skills."""
    skills_root = install_root(project_root)
    recorded = record_io.read(project_record_path(project_root)).installed
    user_skills = discover_user_skills(project_root)
    agents = [a.name for a in manifest.agents]

    names: list[str] = [s.name for s in flatten(manifest)]
    for name in user_skills:
        if name not in names:
            names.append(name)

    statuses: list[SkillStatus] = []
    for name in names:
        materialised = (skills_root / name).exists()

        # `broken` means "we set this up and it is now inconsistent", never
        # "not set up yet" — the two need different advice, and telling someone
        # to run `doctor` when they simply have not run `install` is a dead end.
        if name in recorded and not materialised:
            statuses.append(
                SkillStatus(
                    name,
                    SkillState.BROKEN,
                    "recorded as installed, but its directory is gone",
                )
            )
            continue

        if not materialised:
            # A skill dropped into user_skills is an explicit local choice, so
            # it does not defer to the global layer — it is simply not
            # installed yet.
            if name not in user_skills and global_skill_dir(name, home).is_dir():
                statuses.append(SkillStatus(name, SkillState.GLOBAL))
            else:
                statuses.append(SkillStatus(name, SkillState.MISSING))
            continue

        # Materialised — but an agent that cannot reach it is not being served.
        broken_for = [
            agent for agent in agents if not _fanout_ok(project_root, agent, name)
        ]
        if broken_for:
            statuses.append(
                SkillStatus(
                    name,
                    SkillState.BROKEN,
                    f"fan-out missing or unmanaged for {', '.join(broken_for)}",
                )
            )
        else:
            statuses.append(
                SkillStatus(
                    name,
                    SkillState.USER if name in user_skills else SkillState.PROJECT,
                )
            )

    return Inventory(skills=statuses)


def _fanout_ok(project_root: Path, agent: str, name: str) -> bool:
    link = agent_skill_dir(project_root, agent, name)
    if link.is_symlink():
        return is_managed_fanout(link, project_root)
    return link.exists()


__all__ = ["Inventory", "SkillState", "SkillStatus", "take_inventory"]
