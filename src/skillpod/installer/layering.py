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


# Add an agent here only with a citation and a date. An entry that turns out to
# be wrong causes skills to go missing, which is far worse than the duplicate
# copy that `UNKNOWN` costs.
#
# claude — verified 2026-07-21 against https://code.claude.com/docs/en/skills,
#   and observed directly: a session with both `.claude/skills/` and
#   `~/.claude/skills/` populated could invoke skills from both.
# codex — verified 2026-07-21 against the loader in
#   openai/codex `codex-rs/core-skills/src/loader.rs`. `skill_roots_from_layer_stack`
#   pushes the user roots (`$CODEX_HOME/skills`, marked "Deprecated ... kept for
#   backward compatibility", plus `$HOME/.agents/skills`) alongside the repo
#   roots into one list, so the personal directory is read from inside a project.
# gemini — verified 2026-07-21 against google-gemini/gemini-cli
#   `packages/core/src/skills/skillManager.ts`: `discoverSkills()` loads
#   `Storage.getUserSkillsDir()` (`~/.gemini/skills`) unconditionally at tier 3,
#   before workspace skills at tier 4.
_LAYERING: dict[str, Layering] = {
    "claude": Layering.MERGES,
    "codex": Layering.MERGES,
    "gemini": Layering.MERGES,
}


# Which side wins a *name* collision. Not derivable from `_LAYERING`: all three
# agents below merge, and they resolve a collision three different ways.
#
# claude — "enterprise overrides personal, and personal overrides project"
#   (https://code.claude.com/docs/en/skills, 2026-07-21). The reverse of the
#   usual convention, and the reason `prefer_global: false` warns instead of
#   silently producing a project copy the agent will ignore.
# codex — no override at all: `loader.rs` dedupes roots by *path* only, and the
#   docs say "If two skills share the same `name`, Codex doesn't merge them;
#   both can appear in skill selectors"
#   (https://learn.chatgpt.com/docs/build-skills, 2026-07-21).
# gemini — the project wins: `discoverSkills()` applies workspace skills after
#   user skills into a name-keyed map, so the workspace entry replaces the
#   personal one (2026-07-21).
#
# An unmeasured agent is treated as shadowing, where there is no collision to
# resolve, so `False` is both the default and the correct answer for it.
_PERSONAL_OUTRANKS_PROJECT: dict[str, bool] = {
    "claude": True,
    "codex": False,
    "gemini": False,
}


def layering_for(agent: str) -> Layering:
    return _LAYERING.get(agent, Layering.UNKNOWN)


def merges_layers(agent: str) -> bool:
    return layering_for(agent) is Layering.MERGES


def personal_outranks_project(agent: str) -> bool:
    """True when a personal skill wins a name collision with a project one.

    Deliberately not derived from `merges_layers`: Claude Code is the odd one
    out in letting the personal copy win, and reading the collision rule off
    the merge flag would have warned Codex and Gemini users that their project
    copy is ignored when it is not.
    """
    return _PERSONAL_OUTRANKS_PROJECT.get(agent, False)


__all__ = [
    "Layering",
    "layering_for",
    "merges_layers",
    "personal_outranks_project",
]
