"""Top-level install orchestrator.

Pipeline ordering (per `installer/spec.md`):

    read manifest
        -> resolve sources (with registry fallback)
        -> fetch into cache
        -> materialise .skillpod/skills/<name>
        -> fan out via adapter (symlink/copy/hardlink) to enabled agents
        -> integrity check against lockfile (if any)
        -> write skillfile.lock

A failure in any step rolls back project filesystem state from the
current run.
"""

from __future__ import annotations

import importlib
import logging
import shutil
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_registry import get_adapter, register_adapter, reset_registry
from skillpod.installer.errors import (
    AdapterImportError,
    FrozenDriftError,
    InstallError,
    InstallSystemError,
    InstallUserError,
)
from skillpod.installer.expand import flatten
from skillpod.installer.fanout import (
    create_install_root_symlink,
    materialise_fanout,
    rollback_on_failure,
)
from skillpod.installer.paths import agent_skill_dir, project_skill_dir
from skillpod.installer.resolve import resolve_skill
from skillpod.installer.user_skills import discover_user_skills, resolve_user_skill
from skillpod.lockfile import io as lockfile_io
from skillpod.lockfile.integrity import hash_directory
from skillpod.lockfile.models import LockedSkill, Lockfile
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import AgentEntry, SkillEntry
from skillpod.registry import RegistryError, TrustError
from skillpod.sources.errors import GitOperationError, SourceError
from skillpod.sources.types import ResolvedSkill

logger = logging.getLogger(__name__)


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


def _lockfile_for(report: InstallReport) -> Lockfile:
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
    agent_filter: list[str] | None = None,
) -> InstallReport:
    """Run the full install pipeline against `project_root`.

    `agent_filter`, when provided, restricts fan-out to the named agents
    (intersected with the manifest's `agents:` list). The manifest itself
    is never mutated by this parameter — it only narrows which fan-out
    targets get materialised in this run. Used by `skillpod add ... -a`
    to limit a single install to a subset of agents without rewriting
    the manifest's global `agents:` list.
    """

    project_root = Path(project_root).resolve()
    default_manifest, default_lockfile = _project_paths(project_root)
    manifest_path = (manifest_path or default_manifest).resolve()
    lockfile_path = (lockfile_path or default_lockfile).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise InstallUserError(str(exc)) from exc

    # Phase 0 — register custom adapters BEFORE any filesystem mutation.
    # An import failure aborts the run immediately with a clear error.
    reset_registry()
    _register_manifest_adapters(manifest.agents)

    existing_lock = lockfile_io.read(lockfile_path)
    flat_skills = flatten(manifest)
    user_skills = discover_user_skills(project_root)
    flat_names = {skill.name for skill in flat_skills}
    shadowed = sorted(flat_names & set(user_skills))
    if shadowed:
        warnings.warn(
            ".skillpod/user_skills entries shadow manifest skill(s): "
            + ", ".join(shadowed),
            UserWarning,
            stacklevel=2,
        )

    effective_skills = list(flat_skills)
    for name in user_skills:
        if name not in flat_names:
            effective_skills.append(SkillEntry(name=name))

    # Phase 1 — resolve every skill before mutating the project.
    plan: list[tuple[ResolvedSkill, LockedSkill | None]] = []
    for skill in effective_skills:
        user_skill_path = user_skills.get(skill.name)
        if user_skill_path is not None:
            resolved = resolve_user_skill(skill.name, user_skill_path)
            locked_entry = None
        else:
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
    if agent_filter is not None:
        wanted = set(agent_filter)
        active_agents = [a for a in manifest.agents if a.name in wanted]
        unknown = sorted(wanted - {a.name for a in manifest.agents})
        if unknown:
            raise InstallUserError(
                f"agent_filter references agents not in manifest: {', '.join(unknown)}"
            )
    else:
        active_agents = list(manifest.agents)

    report = InstallReport(
        project_root=project_root,
        manifest_path=manifest_path,
        lockfile_path=lockfile_path,
        fanned_out_to=[a.name for a in active_agents],
    )

    install_mode = InstallMode(manifest.install.mode)
    fallback: list[str] = [str(f) for f in manifest.install.fallback]
    source_violation_reported: set[str] = set()

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

            # Snapshot source_dir mtimes for mutation detection.
            source_snapshot = _snapshot_source(skill_link)

            for agent_entry in active_agents:
                adapter = get_adapter(agent_entry.name)
                target_dir = agent_skill_dir(project_root, agent_entry.name, resolved.name)
                materialise_fanout(
                    skill_name=resolved.name,
                    source_dir=skill_link,
                    target_dir=target_dir,
                    agent=agent_entry.name,
                    project_root=project_root,
                    mode=install_mode,
                    fallback=fallback,
                    adapter=adapter,
                    record=record,
                )

            # Detect any adapter that wrote into source_dir.
            violation_key = resolved.name
            if violation_key not in source_violation_reported:
                _check_source_mutation(skill_link, source_snapshot, violation_key)
                source_violation_reported.add(violation_key)

            report.installed.append(
                InstalledSkill(
                    name=resolved.name,
                    resolved=resolved,
                    project_path=skill_link,
                    sha256=sha256,
                )
            )

    # Phase 3 — write lockfile.
    new_lock = _lockfile_for(report)
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

    for agent_entry in manifest.agents:
        link = agent_skill_dir(project_root, agent_entry.name, skill_name)
        if link.is_symlink():
            link.unlink()


def _register_manifest_adapters(agents: list[AgentEntry]) -> None:
    """Import and register custom adapters declared in the manifest.

    Called before any filesystem mutation.  An import or attribute lookup
    failure raises ``AdapterImportError`` immediately.
    """
    for entry in agents:
        if entry.adapter is None:
            continue
        dotted = entry.adapter
        # Support both "module.ClassName" and "module:ClassName" separators.
        if ":" in dotted:
            module_path, attr = dotted.rsplit(":", 1)
        else:
            module_path, _, attr = dotted.rpartition(".")
        if not module_path:
            raise AdapterImportError(
                f"invalid adapter path {dotted!r} for agent {entry.name!r}: "
                f"must be a dotted module path ending with a class name"
            )
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            raise AdapterImportError(
                f"could not import adapter module {module_path!r} "
                f"for agent {entry.name!r}: {exc}"
            ) from exc
        try:
            cls = getattr(mod, attr)
        except AttributeError as exc:
            raise AdapterImportError(
                f"adapter module {module_path!r} has no attribute {attr!r} "
                f"for agent {entry.name!r}"
            ) from exc
        try:
            instance = cls()
        except Exception as exc:
            raise AdapterImportError(
                f"could not instantiate adapter {dotted!r} "
                f"for agent {entry.name!r}: {exc}"
            ) from exc
        register_adapter(entry.name, instance)
        logger.debug("registered adapter %s for agent %s", dotted, entry.name)


def _snapshot_source(source_dir: Path) -> dict[Path, tuple[float, int]]:
    """Return a mapping of ``{path: (mtime, size)}`` for all files under source_dir."""
    snapshot: dict[Path, tuple[float, int]] = {}
    if not source_dir.exists():
        return snapshot
    for item in source_dir.rglob("*"):
        if item.is_file() and not item.is_symlink():
            try:
                st = item.stat()
                snapshot[item] = (st.st_mtime, st.st_size)
            except OSError:
                pass
    return snapshot


def _check_source_mutation(
    source_dir: Path,
    snapshot: dict[Path, tuple[float, int]],
    skill_name: str,
) -> None:
    """Emit an error-severity warning if any file in source_dir changed.

    A misbehaving adapter that writes into source_dir violates the adapter
    contract.  We detect this post-fan-out and report it so the user can
    fix their adapter.  The run still raises SystemExit(1) via the warning.
    """
    violations: list[str] = []
    if not source_dir.exists():
        return
    for item in source_dir.rglob("*"):
        if item.is_file() and not item.is_symlink():
            try:
                st = item.stat()
                before = snapshot.get(item)
                if before is None or (st.st_mtime, st.st_size) != before:
                    violations.append(str(item))
            except OSError:
                pass
    if violations:
        msg = (
            f"[ERROR] adapter-source-mutation: a custom adapter wrote into "
            f"source_dir for skill '{skill_name}': "
            + ", ".join(violations)
        )
        warnings.warn(msg, UserWarning, stacklevel=3)
        raise InstallSystemError(
            f"adapter contract violation: source_dir was mutated for skill '{skill_name}'"
        )


__all__ = [
    "InstallError",
    "InstallReport",
    "InstalledSkill",
    "install",
    "uninstall",
]
