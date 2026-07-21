"""Snapshot the current global skill set into a profile.

Records every skill currently managed-fanned-out to an agent, recovering each
one's source **best-effort** so the resulting profile is portable:

- ``~/.skillpod/skills/<name>`` is a symlink into the git cache
  (``~/.cache/skillpod/<host>/<owner>/<repo>@<commit>/<subpath>``) → reconstruct
  an ``owner/repo`` (or ``https://<host>/<repo>``) source with ``ref`` + ``subpath``.
- the symlink points at a local directory → use that path as a local source.
- it is a real-directory copy with no recoverable origin → name-only (no source),
  which still works on this machine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from skillpod.installer.global_apply import managed_global_skills
from skillpod.installer.global_install import DEFAULT_GLOBAL_AGENTS
from skillpod.installer.global_record import read_global_record
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_profile_path,
    global_skill_dir,
    is_managed_global_fanout,
)
from skillpod.profile.models import GlobalProfileBody, GlobalProfileSkill
from skillpod.sources.cache import cache_root


def _recover_from_cache_path(target: Path) -> GlobalProfileSkill | None:
    """Reconstruct a source from a cache-dir symlink target, or None."""
    try:
        rel = target.relative_to(cache_root())
    except ValueError:
        return None
    parts = rel.parts
    at_idx = next((i for i, p in enumerate(parts) if "@" in p), None)
    if at_idx is None or at_idx == 0:
        return None
    host = parts[0]
    repo_seg, _, commit = parts[at_idx].partition("@")
    repo_path = "/".join([*parts[1:at_idx], repo_seg])
    subpath = "/".join(parts[at_idx + 1 :]) or None
    source = repo_path if host == "github.com" else f"https://{host}/{repo_path}"
    name = subpath.rsplit("/", 1)[-1] if subpath else repo_path.rsplit("/", 1)[-1]
    return GlobalProfileSkill(name=name, source=source, ref=commit or None, subpath=subpath)


def recover_source(name: str, home: Path | None = None) -> GlobalProfileSkill:
    """Best-effort recover the source of an installed global skill.

    The install record is consulted first and is authoritative when it knows
    the skill — that is the whole reason it exists. Everything below it is
    archaeology for skills installed before provenance was recorded.

    A recorded ``ref`` is preferred over the ``commit`` it resolved to, so a
    saved profile tracks the branch rather than freezing at whatever was
    current on this machine. The commit is only used when no ref is known.
    """
    recorded = read_global_record(home).installed.get(name)
    if recorded is not None and recorded.source:
        if recorded.kind == "local":
            return GlobalProfileSkill(name=name, source=recorded.source)
        return GlobalProfileSkill(
            name=name,
            source=recorded.source,
            ref=recorded.ref or recorded.commit,
            subpath=recorded.subpath,
        )

    skill_dir = global_skill_dir(name, home)
    if skill_dir.is_symlink():
        raw = os.readlink(skill_dir)
        if raw.startswith("\\\\?\\"):
            raw = raw[4:]
        target = Path(raw)
        if not target.is_absolute():
            target = (skill_dir.parent / target).resolve(strict=False)
        recovered = _recover_from_cache_path(target)
        if recovered is not None:
            return GlobalProfileSkill(
                name=name,
                source=recovered.source,
                ref=recovered.ref,
                subpath=recovered.subpath,
            )
        # Local symlink: use the target directory as a local source.
        return GlobalProfileSkill(name=name, source=str(target))
    # Real-directory copy predating the record → genuinely unknown. Saying so
    # is the honest answer; `skillpod global update` reports these rather than
    # pretending it can refresh them.
    return GlobalProfileSkill(name=name)


def current_global_agents(home: Path | None = None) -> list[str]:
    """Agents that currently have at least one managed global fan-out.

    Profiles no longer record agents (those are chosen at switch time), but
    this is still useful for the undo history, which must restore the previous
    skills to the agents they were actually on.
    """
    result: list[str] = []
    for agent in DEFAULT_GLOBAL_AGENTS:
        base = (home or Path.home()).expanduser() / f".{agent}" / "skills"
        if not base.is_dir():
            continue
        if any(
            is_managed_global_fanout(global_agent_skill_dir(agent, c.name, home), c.name, home)
            for c in base.iterdir()
        ):
            result.append(agent)
    return result


def snapshot_current_global(
    home: Path | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> GlobalProfileBody:
    """Capture the current managed global skill set as a profile body.

    Agents are intentionally not recorded — a global profile is just a skill
    set; which agents to install to is chosen at switch time.
    """
    names = sorted(managed_global_skills(home))
    skills = [recover_source(n, home) for n in names]
    return GlobalProfileBody(name=name, description=description, skills=skills)


def _skill_to_yaml(skill: GlobalProfileSkill) -> Any:
    if skill.source is None and skill.ref is None and skill.subpath is None:
        return skill.name
    body: dict[str, Any] = {"name": skill.name}
    if skill.source is not None:
        body["source"] = skill.source
    if skill.ref is not None:
        body["ref"] = skill.ref
    if skill.subpath is not None:
        body["subpath"] = skill.subpath
    return body


def serialize_profile_body(body: GlobalProfileBody) -> dict[str, Any]:
    """Render a ``GlobalProfileBody`` to a ``{version, profile}`` YAML mapping."""
    profile: dict[str, Any] = {}
    if body.name is not None:
        profile["name"] = body.name
    if body.description is not None:
        profile["description"] = body.description
    if body.type is not None:
        profile["type"] = body.type
    if body.agents:
        profile["agents"] = list(body.agents)
    profile["skills"] = [_skill_to_yaml(s) for s in body.skills]
    return {"version": 1, "profile": profile}


def write_global_profile_body(
    name: str, body: GlobalProfileBody, home: Path | None = None
) -> Path:
    """Serialise a source-bearing ``GlobalProfileBody`` to its profile file."""
    path = global_profile_path(name, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            serialize_profile_body(body),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


__all__ = [
    "current_global_agents",
    "recover_source",
    "serialize_profile_body",
    "snapshot_current_global",
    "write_global_profile_body",
]
