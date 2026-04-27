"""`skillpod sync` — re-create fan-out entries from the lockfile.

Sync is the offline counterpart to `install`:
- It does not consult the registry.
- It does not mutate the lockfile.
- It can be re-run repeatedly without producing a diff after the first run.

For local-sourced skills (which have no lockfile entry) sync still has
to consult the manifest's source list, but it only walks declared
sources — never the registry.

The optional ``--agent <id>`` flag restricts fan-out cleanup and
re-render to a single agent, leaving all other agents untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer import (
    create_install_root_symlink,
    create_managed_fanout_symlink,
    project_skill_dir,
)
from skillpod.installer.errors import InstallUserError
from skillpod.installer.expand import flatten
from skillpod.installer.fanout import rollback_on_failure
from skillpod.installer.paths import agent_skill_dir
from skillpod.installer.user_skills import discover_user_skills
from skillpod.lockfile import io as lockfile_io
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SkillEntry, SourceEntry
from skillpod.sources.git import populate_cache
from skillpod.sources.local import resolve_local


def _populate_from_lock(lock_url: str, commit: str) -> Path:
    return populate_cache(lock_url, commit)


def _project_path_from_local(project_root: Path, skill_name: str, manifest_sources: list[SourceEntry]) -> Path:
    """Find the local source providing `skill_name` and return its absolute path."""
    for src in sorted(manifest_sources, key=lambda s: s.priority, reverse=True):
        if src.type != "local":
            continue
        try:
            resolved = resolve_local(skill_name, src)
        except Exception:
            continue
        return resolved.path
    raise FileNotFoundError(
        f"sync: no local source provides {skill_name!r} (and skill is not in lockfile)"
    )


def _sync_impl(
    project_root: Path,
    manifest_path: Path,
    *,
    agent_filter: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    all_agent_names = [a.name for a in manifest.agents]

    # Validate --agent flag before touching the filesystem.
    if agent_filter is not None and agent_filter not in all_agent_names:
        raise InstallUserError(
            f"unknown agent {agent_filter!r}; manifest declares: "
            + (", ".join(repr(a) for a in all_agent_names) or "(none)")
        )

    # Agents to re-render (may be a single one when --agent is supplied).
    active_agents = (
        [agent_filter] if agent_filter is not None else all_agent_names
    )

    lock = lockfile_io.read(project_root / "skillfile.lock")
    user_skills = discover_user_skills(project_root)
    skills = flatten(manifest)
    skill_names = {skill.name for skill in skills}
    for name in user_skills:
        if name not in skill_names:
            skills.append(SkillEntry(name=name))
            skill_names.add(name)

    rebuilt: list[str] = []
    with rollback_on_failure() as record:
        for skill in skills:
            locked = lock.resolved.get(skill.name)
            if skill.name in user_skills:
                target = user_skills[skill.name]
            elif locked is not None:
                cache_dir = _populate_from_lock(locked.url, locked.commit)
                target = (cache_dir / skill.name).resolve()
            else:
                target = _project_path_from_local(project_root, skill.name, manifest.sources)

            skill_link = project_skill_dir(project_root, skill.name)
            create_install_root_symlink(skill_link, target, record=record)

            for agent_name in active_agents:
                fanout = agent_skill_dir(project_root, agent_name, skill.name)
                create_managed_fanout_symlink(fanout, skill_link, project_root, record=record)
            rebuilt.append(skill.name)

    return {
        "ok": True,
        "synced": rebuilt,
        "agents": active_agents,
    }


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    agent: str | None = None,
) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    payload = run_with_exit_codes(
        lambda: _sync_impl(project_root, manifest_path, agent_filter=agent),
        json_output=json_output,
    )
    human = (
        f"Synced {len(payload['synced'])} skill(s) to: {', '.join(payload['agents']) or '(no agents)'}"
        if payload["synced"]
        else "Nothing to sync (no skills declared)."
    )
    emit(payload, json_output=json_output, human=human)


__all__ = ["run"]
