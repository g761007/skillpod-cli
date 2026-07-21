"""What each agent does when a skill exists both globally and in a project.

`install.prefer_global` rests entirely on one claim: that an agent reading
``<project>/.<agent>/skills/`` *also* reads ``~/.<agent>/skills/``. Where that
is false, skipping the project install would silently deprive the agent of a
skill the project recommends — a failure the user would experience as "skillpod
didn't install it" with no error to explain why.

So the claim is not assumed per agent. It is recorded here only once measured,
and everything unmeasured is treated as **not merging**, which costs a
redundant copy and nothing else.
"""

from __future__ import annotations

from enum import StrEnum


class Layering(StrEnum):
    """How an agent combines its personal and project skill directories."""

    MERGES = "merges"
    """Both directories are live at once."""

    SHADOWS = "shadows"
    """The project directory replaces the personal one."""

    UNKNOWN = "unknown"
    """Not measured. Treated as `SHADOWS` — the conservative reading."""


# Verified 2026-07-21 against https://code.claude.com/docs/en/skills, and
# observed directly: a session with `.claude/skills/` and `~/.claude/skills/`
# populated could invoke skills from both.
#
# The docs also state the collision rule, which is the reverse of the usual
# convention: "enterprise overrides personal, and personal overrides project".
# That is why `prefer_global: false` warns rather than silently producing a
# project copy the agent will ignore.
#
# Add an agent here only with a citation and a date. An entry that turns out to
# be wrong causes skills to go missing, which is far worse than the duplicate
# copy that `UNKNOWN` costs.
_LAYERING: dict[str, Layering] = {
    "claude": Layering.MERGES,
}


def layering_for(agent: str) -> Layering:
    return _LAYERING.get(agent, Layering.UNKNOWN)


def merges_layers(agent: str) -> bool:
    return layering_for(agent) is Layering.MERGES


def personal_outranks_project(agent: str) -> bool:
    """True when a personal skill wins a name collision with a project one.

    Only meaningful for agents that merge; a shadowing agent has no collision
    to resolve. Currently true for every merging agent we know of.
    """
    return merges_layers(agent)


__all__ = [
    "Layering",
    "layering_for",
    "merges_layers",
    "personal_outranks_project",
]
