"""`skillpod sync` — re-create symlinks from the lockfile.

Sync is the offline counterpart to `install`:
- It does not consult the registry.
- It does not mutate the lockfile.
- It can be re-run repeatedly without producing a diff after the first run.

For local-sourced skills (which have no lockfile entry) sync still has
to consult the manifest's source list, but it only walks declared
sources — never the registry.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer import (
    create_install_root_symlink,
    create_managed_fanout_symlink,
    project_skill_dir,
)
from skillpod.installer.fanout import rollback_on_failure
from skillpod.installer.paths import agent_skill_dir
from skillpod.lockfile import io as lockfile_io
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SourceEntry
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


def _sync_impl(project_root: Path, manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    lock = lockfile_io.read(project_root / "skillfile.lock")

    rebuilt: list[str] = []
    with rollback_on_failure() as record:
        for skill in manifest.skills:
            locked = lock.resolved.get(skill.name)
            if locked is not None:
                cache_dir = _populate_from_lock(locked.url, locked.commit)
                target = (cache_dir / skill.name).resolve()
            else:
                target = _project_path_from_local(project_root, skill.name, manifest.sources)

            skill_link = project_skill_dir(project_root, skill.name)
            create_install_root_symlink(skill_link, target, record=record)

            for agent in manifest.agents:
                fanout = agent_skill_dir(project_root, agent, skill.name)
                create_managed_fanout_symlink(fanout, skill_link, project_root, record=record)
            rebuilt.append(skill.name)

    return {
        "ok": True,
        "synced": rebuilt,
        "agents": list(manifest.agents),
    }


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    payload = run_with_exit_codes(
        lambda: _sync_impl(project_root, manifest_path),
        json_output=json_output,
    )
    human = (
        f"Synced {len(payload['synced'])} skill(s) to: {', '.join(payload['agents']) or '(no agents)'}"
        if payload["synced"]
        else "Nothing to sync (no skills declared)."
    )
    emit(payload, json_output=json_output, human=human)


__all__ = ["run"]
