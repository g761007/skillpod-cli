"""Top-level install orchestrator.

Pipeline ordering (per `installer/spec.md`):

    read manifest
        -> skip skills the record already accounts for
        -> resolve the rest (with registry fallback)
        -> fetch into cache
        -> materialise .skillpod/skills/<name>
        -> fan out via adapter (symlink/copy/hardlink) to enabled agents
        -> write .skillpod/installed.yml

A failure in any step rolls back project filesystem state from the
current run.

``install`` means **make reality match the recommendation**: bring in what is
missing and leave alone what is already there. It never reaches for the
network on behalf of a skill that is already installed and still matches what
the manifest declares. Refreshing to newer upstream content is
``skillpod update`` — a separate, explicit act.
"""

from __future__ import annotations

import importlib
import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from skillpod.fsutil import rmtree
from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_registry import get_adapter, register_adapter, reset_registry
from skillpod.installer.errors import (
    AdapterImportError,
    InstallError,
    InstallSystemError,
    InstallUserError,
)
from skillpod.installer.expand import flatten
from skillpod.installer.fanout import (
    materialise_fanout,
    materialise_install_root,
    rollback_on_failure,
)
from skillpod.installer.layering import merges_layers, personal_outranks_project
from skillpod.installer.paths import (
    agent_skill_dir,
    global_skill_dir,
    project_record_path,
    project_skill_dir,
)
from skillpod.installer.resolve import resolve_skill
from skillpod.installer.user_skills import discover_user_skills, resolve_user_skill
from skillpod.integrity import hash_directory
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import AgentEntry, SkillEntry, SourceEntry
from skillpod.record import io as record_io
from skillpod.record.migrate import LEGACY_LOCKFILE, migrate_lockfile
from skillpod.record.models import InstallRecord, SkillRecord
from skillpod.registry import RegistryError, TrustError
from skillpod.skillset.compose import compose_effective_skillset
from skillpod.sources.errors import GitOperationError, SourceError
from skillpod.sources.types import ResolvedSkill

logger = logging.getLogger(__name__)


@dataclass
class InstalledSkill:
    name: str
    resolved: ResolvedSkill
    project_path: Path
    sha256: str  # every materialised skill gets a digest, local included


@dataclass
class InstallReport:
    project_root: Path
    manifest_path: Path
    record_path: Path
    installed: list[InstalledSkill] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    hidden_by_profile: list[str] = field(default_factory=list)
    satisfied_by_global: list[str] = field(default_factory=list)
    shadowed_by_global: dict[str, list[str]] = field(default_factory=dict)
    fanned_out_to: list[str] = field(default_factory=list)


def _project_paths(project_root: Path) -> tuple[Path, Path]:
    return (
        project_root / "skillfile.yml",
        project_record_path(project_root),
    )


def _record_entry(entry: InstalledSkill) -> SkillRecord:
    """Describe one materialised skill for the install record."""
    resolved = entry.resolved
    if resolved.source_kind == "local":
        # Local skills are recorded by the directory they were copied from.
        # The lockfile could not express this at all; a record has nothing to
        # pin, so there is no reason to omit them.
        return SkillRecord(
            kind="local",
            source=str(resolved.path),
            sha256=entry.sha256,
        )
    return SkillRecord(
        kind=resolved.source_kind,
        source=resolved.url,
        ref=resolved.ref,
        commit=resolved.commit,
        sha256=entry.sha256,
    )


def _satisfied_by_global(
    skill_name: str,
    agents: list[AgentEntry],
    *,
    prefer_global: bool,
    home: Path | None = None,
) -> bool:
    """True when the user's global install already covers this recommendation.

    Requires *every* declared agent to merge its personal and project skill
    directories. One agent that does not would simply never see the skill, and
    a silently missing skill is a far worse outcome than a redundant copy — so
    an unmeasured agent blocks the optimisation rather than gambling on it.
    """
    if not prefer_global or not agents:
        return False
    if not all(merges_layers(agent.name) for agent in agents):
        return False
    return global_skill_dir(skill_name, home).is_dir()


def _shadowed_by_global(
    skill_name: str, agents: list[AgentEntry], *, home: Path | None = None
) -> list[str]:
    """Agents whose personal copy will outrank the project copy we just made.

    Only reachable with ``prefer_global: false``. Claude Code documents
    "personal overrides project", so the project copy is materialised and then
    ignored — worth saying out loud rather than leaving the user to wonder why
    their pinned version has no effect.
    """
    if not global_skill_dir(skill_name, home).is_dir():
        return []
    return [a.name for a in agents if personal_outranks_project(a.name)]


def _already_satisfied(
    skill: SkillEntry,
    source_map: dict[str, SourceEntry],
    existing: SkillRecord | None,
    skills_root: Path,
) -> bool:
    """True when `skill` needs no work — already installed, still matching.

    Answering *without touching the network* is the point: a project whose
    skills are all present should re-`install` offline and instantly. Anything
    that might have changed upstream is deliberately not considered, because
    chasing upstream is what ``skillpod update`` is for.
    """
    if existing is None or not (skills_root / skill.name).is_dir():
        return False

    # Local sources are cheap to re-read and the user may have edited them
    # in place, so they are never skipped.
    if existing.kind == "local":
        return False

    # An authored pin is the one thing that must still agree.
    if skill.version is not None:
        return existing.commit == skill.version

    if skill.source is not None:
        declared = source_map.get(skill.source)
        if declared is None or declared.type != "git":
            return False
        if existing.source != declared.url:
            return False
        # A record with no ref came from the retired lockfile, which never
        # stored one. Unknown is not evidence of a mismatch — treating it as
        # one would re-download every skill in every migrated project, which
        # is exactly what seeding the record from the lockfile prevents.
        # `skillpod update` re-resolves and fills the ref in properly.
        return existing.ref is None or existing.ref == declared.ref

    # Registry-resolved or probed: a record plus a materialised directory is
    # enough. `skillpod update` is how the user asks for something newer.
    return True


def install(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    record_path: Path | None = None,
    agent_filter: list[str] | None = None,
    refresh: bool | list[str] = False,
    home: Path | None = None,
) -> InstallReport:
    """Run the full install pipeline against `project_root`.

    `agent_filter`, when provided, restricts fan-out to the named agents
    (intersected with the manifest's `agents:` list). The manifest itself
    is never mutated by this parameter — it only narrows which fan-out
    targets get materialised in this run. Used by `skillpod add ... -a`
    to limit a single install to a subset of agents without rewriting
    the manifest's global `agents:` list.

    `refresh` opts out of the already-satisfied skip: ``True`` re-resolves
    everything, a list re-resolves only those names. This is how
    `skillpod update` asks for newer upstream content — `install` on its own
    never does.
    """

    project_root = Path(project_root).resolve()
    default_manifest, default_record = _project_paths(project_root)
    manifest_path = (manifest_path or default_manifest).resolve()
    record_path = (record_path or default_record).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise InstallUserError(str(exc)) from exc

    # Phase 0 — register custom adapters BEFORE any filesystem mutation.
    # An import failure aborts the run immediately with a clear error.
    reset_registry()
    _register_manifest_adapters(manifest.agents)

    existing_record = record_io.read(record_path)
    if not existing_record.installed:
        # First run in a project that predates install records: seed from the
        # legacy lockfile so an established project does not re-download
        # everything. The lockfile itself is left in place for the user to
        # remove — it is committed, and deleting it is not ours to decide.
        migrated = migrate_lockfile(project_root)
        if migrated is not None:
            existing_record = migrated
            logger.info(
                "seeded install record from %s; you can now `git rm %s`",
                LEGACY_LOCKFILE,
                LEGACY_LOCKFILE,
            )

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

    # Phase 1 — decide what needs work, then resolve only that, before
    # mutating anything. Skipped skills never reach the network.
    source_map = {s.name: s for s in manifest.sources}
    skills_root = project_root / ".skillpod" / "skills"
    plan: list[ResolvedSkill] = []
    skipped: list[str] = []
    satisfied_by_global: list[str] = []
    shadowed_by_global: dict[str, list[str]] = {}

    for skill in effective_skills:
        user_skill_path = user_skills.get(skill.name)
        if user_skill_path is not None:
            plan.append(resolve_user_skill(skill.name, user_skill_path))
            continue

        # Checked before anything else: a recommendation the user already
        # satisfies globally needs no resolution, no download, and no copy.
        if _satisfied_by_global(
            skill.name, manifest.agents, prefer_global=manifest.install.prefer_global, home=home
        ):
            satisfied_by_global.append(skill.name)
            continue

        eclipsed = _shadowed_by_global(skill.name, manifest.agents, home=home)
        if eclipsed:
            shadowed_by_global[skill.name] = eclipsed

        wants_refresh = refresh is True or (
            isinstance(refresh, list) and skill.name in refresh
        )
        if not wants_refresh and _already_satisfied(
            skill, source_map, existing_record.installed.get(skill.name), skills_root
        ):
            skipped.append(skill.name)
            continue

        try:
            plan.append(resolve_skill(skill, manifest))
        except TrustError as exc:
            raise InstallUserError(str(exc)) from exc
        except RegistryError as exc:
            raise InstallSystemError(f"registry: {exc}") from exc
        except GitOperationError as exc:
            raise InstallSystemError(f"git: {exc}") from exc
        except SourceError as exc:
            raise InstallUserError(str(exc)) from exc

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
        record_path=record_path,
        skipped=skipped,
        satisfied_by_global=satisfied_by_global,
        shadowed_by_global=shadowed_by_global,
        fanned_out_to=[a.name for a in active_agents],
    )

    # Resolved before any mutation so a bad profile name fails fast.
    visible = {
        s.name
        for s in compose_effective_skillset(manifest, project_root, home=home).skills
    }
    hidden_by_profile: list[str] = []

    install_mode = InstallMode(manifest.install.mode)
    fallback: list[str] = [str(f) for f in manifest.install.fallback]
    source_violation_reported: set[str] = set()

    with rollback_on_failure() as rollback:
        for resolved in plan:
            skill_link = project_skill_dir(project_root, resolved.name)
            materialise_install_root(
                skill_link,
                resolved.path,
                skill_name=resolved.name,
                record=rollback,
            )

            # Every materialised skill gets a digest, local included — the
            # record describes what is on disk, and local content is on disk.
            sha256 = hash_directory(skill_link)

            # Snapshot source_dir mtimes for mutation detection.
            source_snapshot = _snapshot_source(skill_link)

            # The active profile decides visibility, not presence: the skill is
            # materialised either way, so switching back needs no download.
            # Without this, `install` would re-link a skill the user had just
            # hidden with `skillpod switch`.
            if resolved.name not in visible:
                hidden_by_profile.append(resolved.name)
                report.installed.append(
                    InstalledSkill(
                        name=resolved.name,
                        resolved=resolved,
                        project_path=skill_link,
                        sha256=sha256,
                    )
                )
                continue

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
                    record=rollback,
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

    report.hidden_by_profile = hidden_by_profile

    # Phase 3 — write the install record. Skipped skills keep the entry they
    # already had; nothing was re-resolved for them, so nothing changed.
    entries = {
        name: existing_record.installed[name]
        for name in skipped
        if name in existing_record.installed
    }
    for entry in report.installed:
        entries[entry.name] = _record_entry(entry)
    try:
        record_io.write(record_path, InstallRecord(installed=entries))
    except OSError as exc:
        raise InstallSystemError(f"failed to write install record: {exc}") from exc

    return report


def uninstall(
    project_root: Path,
    skill_name: str,
    *,
    manifest_path: Path | None = None,
) -> None:
    """Remove `<.skillpod/skills/<name>>` and every managed agent fan-out symlink.

    Caller is responsible for editing the manifest and the install record;
    this function only operates on filesystem artefacts.
    """
    project_root = Path(project_root).resolve()
    default_manifest, _ = _project_paths(project_root)
    manifest_path = (manifest_path or default_manifest).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise InstallUserError(str(exc)) from exc

    skill_link = project_skill_dir(project_root, skill_name)
    if skill_link.is_symlink() or skill_link.exists():
        if skill_link.is_symlink():
            skill_link.unlink()
        else:
            rmtree(skill_link)

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
