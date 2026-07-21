"""Apply a global profile: reconcile global fan-out to match the profile.

Activating a global profile materialises exactly that profile's skills into the
per-agent global skill directories (``~/.<agent>/skills/``). Skills missing from
``~/.skillpod/skills/`` are downloaded from their inline source first; managed
fan-out for skills the profile no longer lists is unlinked (the install-root
cache copy is kept so re-activation needs no download).

Reconcile is *content-addressed by skill name*: a profile skill's ``name`` must
match the discovered skill name in its source (selecting one of several in a
multi-skill repo, or the derived name of a root-is-skill repo).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path

from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.installer.global_install import (
    DEFAULT_GLOBAL_AGENTS,
    install_global,
    materialise_agent_link,
    unlink_global_fanout,
)
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_install_root,
    global_skill_dir,
    is_managed_global_fanout,
)
from skillpod.profile.errors import ProfileError
from skillpod.profile.models import GlobalProfileBody, GlobalProfileSkill
from skillpod.sources.discovery import discover_skills
from skillpod.sources.errors import SourceError
from skillpod.sources.git import (
    populate_cache,
    resolve_default_branch,
    resolve_ref,
)
from skillpod.sources.spec import SourceSpec, parse_source_spec


@dataclass
class ApplyPlan:
    """The reconciliation diff between the current global state and a profile."""

    agents: list[str]
    to_download: list[GlobalProfileSkill] = field(default_factory=list)
    to_link: list[str] = field(default_factory=list)
    to_unlink: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.to_download or self.to_link or self.to_unlink)


@dataclass
class ApplyReport:
    """What `execute_apply` actually changed."""

    agents: list[str]
    downloaded: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    unlinked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _present_in_cache(home: Path | None) -> set[str]:
    root = global_install_root(home)
    if not root.is_dir():
        return set()
    return {c.name for c in root.iterdir() if c.is_dir()}


def _fully_linked(name: str, agents: list[str], home: Path | None) -> bool:
    return all(
        is_managed_global_fanout(global_agent_skill_dir(a, name, home), name, home)
        for a in agents
    )


def managed_global_skills(home: Path | None = None) -> set[str]:
    """Skill names currently managed-fanned-out to any supported agent.

    This is the set treated as "the active global skill set" — used by profile
    snapshotting and history.
    """
    return _managed_fanned_out(list(DEFAULT_GLOBAL_AGENTS), home)


def _managed_fanned_out(agents: list[str], home: Path | None) -> set[str]:
    """Skill names currently managed-fanned-out to any of ``agents``."""
    base = (home or Path.home()).expanduser()
    names: set[str] = set()
    for agent in agents:
        root = base / f".{agent}" / "skills"
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if is_managed_global_fanout(child, child.name, home):
                names.add(child.name)
    return names


def plan_apply(
    body: GlobalProfileBody,
    *,
    agents: list[str] | None = None,
    home: Path | None = None,
) -> ApplyPlan:
    """Compute the reconciliation diff for applying ``body`` to ``agents``.

    ``agents`` is chosen at call time (the CLI's ``--agent`` flag); it defaults
    to every supported agent. The profile's own ``agents`` field, if any, is
    not used for targeting.

    - cache-missing skill with a source  → ``to_download``
    - cache-missing skill with no source → ``unresolved``
    - cached skill not fully fanned out  → ``to_link``
    - managed fan-out not in the profile → ``to_unlink``
    """
    agents = list(agents) if agents else list(DEFAULT_GLOBAL_AGENTS)
    present = _present_in_cache(home)
    desired = {s.name for s in body.skills}

    plan = ApplyPlan(agents=agents)
    for skill in body.skills:
        if skill.name not in present:
            if skill.source:
                plan.to_download.append(skill)
            else:
                plan.unresolved.append(skill.name)
        elif not _fully_linked(skill.name, agents, home):
            plan.to_link.append(skill.name)

    fanned = _managed_fanned_out(list(DEFAULT_GLOBAL_AGENTS), home)
    plan.to_unlink = sorted(fanned - desired)
    return plan


def _download_skill(skill: GlobalProfileSkill, agents: list[str], *, force: bool, home: Path | None) -> None:
    """Resolve ``skill`` from its inline source and install it globally."""
    if not skill.source:
        raise ProfileError(f"skill '{skill.name}': no source to download from")
    spec = parse_source_spec(skill.source, ref=skill.ref)
    if spec is None:
        raise ProfileError(
            f"skill '{skill.name}': source '{skill.source}' is not a recognised "
            "git URL, owner/repo, or local path"
        )
    if skill.subpath:
        spec = replace(spec, subpath=skill.subpath)

    # Fetch + discover so we can select the named skill out of the source.
    spec, root, _commit = fetch_source(spec)
    discovered = discover_skills(root, root_name=spec.derived_name)
    match = next((d for d in discovered if d.name == skill.name), None)
    if match is None:
        available = ", ".join(d.name for d in discovered) or "<none>"
        raise ProfileError(
            f"skill '{skill.name}' not found in source '{skill.source}' "
            f"(available: {available})"
        )
    install_global(spec, [match], agents=agents, force=force, home=home)


def execute_apply(
    body: GlobalProfileBody,
    plan: ApplyPlan,
    *,
    force: bool = False,
    home: Path | None = None,
) -> ApplyReport:
    """Carry out ``plan`` so the global fan-out matches ``body``.

    Apply is **best-effort and idempotent, not transactional**: re-running it
    converges on the target state. The steps run in a deliberate order so a
    failure is never destructive — additions happen before removals:

    1. download missing skills (each is also fanned out by ``install_global``)
    2. link already-cached skills onto the target agents
    3. prune target skills from agents the profile does not list
    4. unlink managed skills the profile dropped

    Because the only removal steps (3, 4) run *after* every download/link has
    succeeded, a mid-run download failure raises before anything is removed —
    the previously active skills stay linked, and at worst a few new skills are
    added. The caller writes the active-profile pointer only on full success.

    Skills the profile lists but that are missing from ``~/.skillpod/skills/``
    with no source to download from are **skipped with a warning** (recorded in
    ``report.skipped``), so a legacy name-only profile still applies the skills
    it can resolve instead of failing outright.
    """
    agents = plan.agents
    other_agents = [a for a in DEFAULT_GLOBAL_AGENTS if a not in agents]
    report = ApplyReport(agents=agents)

    for name in plan.unresolved:
        warnings.warn(
            f"skill '{name}' is not installed in ~/.skillpod/skills/ and the "
            "profile gives no source to download it from — skipping",
            stacklevel=2,
        )
        report.skipped.append(name)

    for skill in plan.to_download:
        _download_skill(skill, agents, force=force, home=home)
        report.downloaded.append(skill.name)

    adapter = IdentityAdapter()
    for name in plan.to_link:
        source = global_skill_dir(name, home)
        for agent in agents:
            link = global_agent_skill_dir(agent, name, home)
            link.parent.mkdir(parents=True, exist_ok=True)
            materialise_agent_link(link, source, adapter, InstallMode.SYMLINK, force=force)
        report.linked.append(name)

    # Prune desired skills from agents the profile does not target.
    if other_agents:
        for skill in body.skills:
            unlink_global_fanout(skill.name, agents=other_agents, home=home)

    for name in plan.to_unlink:
        unlink_global_fanout(name, agents=list(DEFAULT_GLOBAL_AGENTS), home=home)
        report.unlinked.append(name)

    return report


def fetch_source(spec: SourceSpec) -> tuple[SourceSpec, Path, str]:
    """Materialise ``spec`` on disk; return ``(resolved_spec, root, commit)``."""
    if spec.kind == "git":
        if spec.ref is None:
            spec = replace(spec, ref=resolve_default_branch(spec.url_or_path))
        assert spec.ref is not None
        commit = resolve_ref(spec.url_or_path, spec.ref)
        repo_root = populate_cache(spec.url_or_path, commit)
        root = repo_root / spec.subpath if spec.subpath else repo_root
        if spec.subpath and not root.is_dir():
            raise SourceError(
                f"subpath {spec.subpath!r} does not exist in {spec.url_or_path}@{commit}"
            )
        return spec, root, commit
    root = Path(spec.url_or_path).expanduser().resolve()
    if not root.is_dir():
        raise SourceError(f"local source path does not exist: {root}")
    return spec, root, ""


__all__ = [
    "ApplyPlan",
    "ApplyReport",
    "execute_apply",
    "fetch_source",
    "managed_global_skills",
    "plan_apply",
]
