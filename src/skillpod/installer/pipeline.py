"""Top-level install orchestrator.

Pipeline ordering (per `installer/spec.md`):

    read manifest
        -> resolve sources (with registry fallback)
        -> fetch into cache
        -> materialise .skillpod/skills/<name>
        -> fan out symlinks to enabled agents
        -> integrity check against lockfile (if any)
        -> write skillfile.lock

A failure in any step rolls back project filesystem state from the
current run.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.errors import (
    FrozenDriftError,
    InstallError,
    InstallSystemError,
    InstallUserError,
)
from skillpod.installer.fanout import (
    create_install_root_symlink,
    create_managed_fanout_symlink,
    rollback_on_failure,
)
from skillpod.installer.paths import agent_skill_dir, project_skill_dir
from skillpod.installer.resolve import resolve_skill
from skillpod.lockfile import io as lockfile_io
from skillpod.lockfile.integrity import hash_directory
from skillpod.lockfile.models import LockedSkill, Lockfile
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import Skillfile
from skillpod.registry import RegistryError, TrustError
from skillpod.sources.errors import GitOperationError, SourceError
from skillpod.sources.types import ResolvedSkill


@dataclass
class InstalledSkill:
    name: str
    resolved: ResolvedSkill
    project_path: Path
    sha256: str | None  # None for local sources (not lockable)


@dataclass
class InstallReport:
    project_root: Path
    manifest_path: Path
    lockfile_path: Path
    installed: list[InstalledSkill] = field(default_factory=list)
    fanned_out_to: list[str] = field(default_factory=list)


def _project_paths(project_root: Path) -> tuple[Path, Path]:
    return (
        project_root / "skillfile.yml",
        project_root / "skillfile.lock",
    )


def _lockfile_for(report: InstallReport, manifest: Skillfile) -> Lockfile:
    resolved: dict[str, LockedSkill] = {}
    for entry in report.installed:
        if entry.resolved.source_kind == "local":
            continue  # local sources are not lockable
        if entry.resolved.url is None or entry.resolved.commit is None:
            continue  # paranoia: shouldn't happen for git/registry kinds
        assert entry.sha256 is not None
        resolved[entry.name] = LockedSkill(
            source="git",
            url=entry.resolved.url,
            commit=entry.resolved.commit,
            sha256=entry.sha256,
        )
    return Lockfile(version=1, resolved=resolved)


def install(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    lockfile_path: Path | None = None,
) -> InstallReport:
    """Run the full install pipeline against `project_root`."""

    project_root = Path(project_root).resolve()
    default_manifest, default_lockfile = _project_paths(project_root)
    manifest_path = (manifest_path or default_manifest).resolve()
    lockfile_path = (lockfile_path or default_lockfile).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise InstallUserError(str(exc)) from exc

    existing_lock = lockfile_io.read(lockfile_path)

    # Phase 1 — resolve every skill before mutating the project.
    plan: list[tuple[ResolvedSkill, LockedSkill | None]] = []
    for skill in manifest.skills:
        locked_entry = existing_lock.resolved.get(skill.name)
        try:
            resolved = resolve_skill(skill, manifest, locked=locked_entry)
        except TrustError as exc:
            raise InstallUserError(str(exc)) from exc
        except RegistryError as exc:
            raise InstallSystemError(f"registry: {exc}") from exc
        except GitOperationError as exc:
            raise InstallSystemError(f"git: {exc}") from exc
        except SourceError as exc:
            raise InstallUserError(str(exc)) from exc

        if locked_entry is not None and resolved.commit != locked_entry.commit:
            raise FrozenDriftError(
                f"frozen mode: {skill.name} resolved to {resolved.commit}, "
                f"but lockfile pins {locked_entry.commit}"
            )
        plan.append((resolved, locked_entry))

    # Phase 2 — materialise and fan out under a rollback guard.
    report = InstallReport(
        project_root=project_root,
        manifest_path=manifest_path,
        lockfile_path=lockfile_path,
        fanned_out_to=list(manifest.agents),
    )

    with rollback_on_failure() as record:
        for resolved, locked_entry in plan:
            skill_link = project_skill_dir(project_root, resolved.name)
            create_install_root_symlink(skill_link, resolved.path, record=record)

            sha256: str | None = None
            if resolved.source_kind != "local":
                sha256 = hash_directory(skill_link)
                if locked_entry is not None and sha256 != locked_entry.sha256:
                    raise FrozenDriftError(
                        f"frozen mode: {resolved.name} content sha256 "
                        f"{sha256} does not match lockfile {locked_entry.sha256}"
                    )

            for agent in manifest.agents:
                fanout_link = agent_skill_dir(project_root, agent, resolved.name)
                create_managed_fanout_symlink(
                    fanout_link, skill_link, project_root, record=record
                )

            report.installed.append(
                InstalledSkill(
                    name=resolved.name,
                    resolved=resolved,
                    project_path=skill_link,
                    sha256=sha256,
                )
            )

    # Phase 3 — write lockfile.
    new_lock = _lockfile_for(report, manifest)
    try:
        lockfile_io.write(lockfile_path, new_lock)
    except OSError as exc:
        raise InstallSystemError(f"failed to write lockfile: {exc}") from exc

    return report


def uninstall(
    project_root: Path,
    skill_name: str,
    *,
    manifest_path: Path | None = None,
    lockfile_path: Path | None = None,
) -> None:
    """Remove `<.skillpod/skills/<name>>` and every managed agent fan-out symlink.

    Caller is responsible for editing the manifest first; this function
    only operates on filesystem artefacts.
    """
    project_root = Path(project_root).resolve()
    default_manifest, default_lockfile = _project_paths(project_root)
    manifest_path = (manifest_path or default_manifest).resolve()
    lockfile_path = (lockfile_path or default_lockfile).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise InstallUserError(str(exc)) from exc

    skill_link = project_skill_dir(project_root, skill_name)
    if skill_link.is_symlink() or skill_link.exists():
        if skill_link.is_symlink():
            skill_link.unlink()
        else:
            shutil.rmtree(skill_link)

    for agent in manifest.agents:
        link = agent_skill_dir(project_root, agent, skill_name)
        if link.is_symlink():
            link.unlink()


__all__ = [
    "InstallError",
    "InstallReport",
    "InstalledSkill",
    "install",
    "uninstall",
]
