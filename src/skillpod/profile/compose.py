"""Compose multiple global profiles into one source-bearing body.

``skillpod switch <a>+<b> --scope global`` unions the operands'
:class:`~skillpod.profile.models.GlobalProfileSkill` lists while **preserving
their inline sources**, so the global-apply path can download and fan out the
combined set.

Semantics (frozen in v0.7.0):

- **Operands are local profile names only.** A remote reference (URL or
  ``owner/repo/file.yml``) inside a ``+`` expression is rejected.
- **Skills union left-to-right, de-duplicated by name.** The leftmost operand
  that declares a skill wins.
- **Same name, different source → left wins with a warning.** When a later
  operand re-declares a skill with a genuinely different ``(source, ref,
  subpath)``, the first source is kept and a :class:`UserWarning` is emitted.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from skillpod.profile.errors import ProfileError
from skillpod.profile.fetch import is_remote_target, resolve_profile_target
from skillpod.profile.models import GlobalProfileBody, GlobalProfileSkill
from skillpod.skillset.compose import parse_profile_expr


def _source_key(skill: GlobalProfileSkill) -> tuple[str | None, str | None, str | None]:
    return (skill.source, skill.ref, skill.subpath)


def compose_global_bodies(
    expr: str,
    *,
    home: Path | None = None,
) -> tuple[str, GlobalProfileBody]:
    """Resolve and union the operands of a ``+`` expression into one body.

    Returns ``(expr, merged_body)`` where ``merged_body`` carries the unioned,
    source-bearing skills. Raises :class:`ProfileError` when the expression is
    empty, an operand is a remote reference, or an operand profile is missing.
    """
    names = parse_profile_expr(expr)
    if not names:
        raise ProfileError(f"empty profile expression: {expr!r}")

    merged_skills: list[GlobalProfileSkill] = []
    by_name: dict[str, GlobalProfileSkill] = {}
    merged_agents: list[str] = []
    seen_agents: set[str] = set()
    merged_type: str | None = None

    for name in names:
        if is_remote_target(name):
            raise ProfileError(
                f"composition operand '{name}' must be a local profile name; "
                "URL / owner-repo operands are not supported in a '+' expression"
            )
        _resolved, body = resolve_profile_target(name, home=home, update=False)

        if merged_type is None and body.type is not None:
            merged_type = body.type

        for skill in body.skills:
            existing = by_name.get(skill.name)
            if existing is None:
                by_name[skill.name] = skill
                merged_skills.append(skill)
            elif _source_key(existing) != _source_key(skill):
                warnings.warn(
                    f"skill '{skill.name}' has conflicting sources across composed "
                    f"profiles; using {existing.source or '<name-only>'} (first wins), "
                    f"ignoring {skill.source or '<name-only>'} (from '{name}')",
                    UserWarning,
                    stacklevel=2,
                )

        for agent in body.agents:
            if agent not in seen_agents:
                merged_agents.append(agent)
                seen_agents.add(agent)

    merged = GlobalProfileBody(
        name=expr,
        type=merged_type,
        agents=merged_agents,
        skills=merged_skills,
    )
    return expr, merged


__all__ = ["compose_global_bodies"]
