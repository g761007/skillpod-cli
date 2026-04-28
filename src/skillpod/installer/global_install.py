"""Global install: materialise skills under `~/.skillpod/skills/` and
fan out to `~/.<agent>/skills/`.

Mirrors the project pipeline's two-step shape (root symlink + per-agent
fan-out) but rooted at the user's home rather than a project. Skips the
manifest entirely — global state is independent of any single project.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.installer.errors import InstallConflict, InstallSystemError
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_install_root,
    global_skill_dir,
)
from skillpod.sources.discovery import DiscoveredSkill
from skillpod.sources.git import populate_cache, resolve_ref
from skillpod.sources.spec import SourceSpec
from skillpod.sources.types import ResolvedSkill

logger = logging.getLogger(__name__)


# Default fan-out targets when the caller does not pass `-a`. Mirrors
# `cli/commands/global_list.GLOBAL_SKILL_DIRS` so the two stay in sync;
# the canonical list lives there.
DEFAULT_GLOBAL_AGENTS: tuple[str, ...] = (
    "claude",
    "codex",
    "gemini",
    "cursor",
    "opencode",
    "antigravity",
)


@dataclass
class GlobalInstalledSkill:
    name: str
    resolved: ResolvedSkill
    install_path: Path
    fanned_out_to: list[str] = field(default_factory=list)


@dataclass
class GlobalInstallReport:
    spec: SourceSpec
    install_root: Path
    installed: list[GlobalInstalledSkill] = field(default_factory=list)


def install_global(
    spec: SourceSpec,
    selected: list[DiscoveredSkill],
    *,
    agents: Iterable[str] | None = None,
    force: bool = False,
    mode: InstallMode = InstallMode.SYMLINK,
    home: Path | None = None,
) -> GlobalInstallReport:
    """Materialise each discovered skill globally and fan out to agents.

    `force=True` replaces an existing `~/.skillpod/skills/<name>` (or
    fan-out symlink) instead of raising `InstallConflict`. Without it,
    a pre-existing entry that skillpod did not create is preserved.
    """
    target_agents = list(agents) if agents is not None else list(DEFAULT_GLOBAL_AGENTS)
    install_root = global_install_root(home)
    install_root.mkdir(parents=True, exist_ok=True)

    if spec.kind == "git":
        commit = resolve_ref(spec.url_or_path, spec.ref)
        repo_root = populate_cache(spec.url_or_path, commit)
    else:
        commit = ""
        repo_root = Path(spec.url_or_path).expanduser().resolve()
        if not repo_root.is_dir():
            raise InstallSystemError(f"local source path does not exist: {repo_root}")

    adapter = IdentityAdapter()
    report = GlobalInstallReport(spec=spec, install_root=install_root)

    for skill in selected:
        skill_source_dir = repo_root if skill.rel_path == "." else repo_root / skill.rel_path
        if not skill_source_dir.is_dir():
            raise InstallSystemError(
                f"skill {skill.name!r}: directory missing in source ({skill_source_dir})"
            )

        install_link = global_skill_dir(skill.name, home)
        _replace_with_symlink(install_link, skill_source_dir, force=force)

        resolved = ResolvedSkill(
            name=skill.name,
            source_kind=spec.kind,
            source_name=spec.derived_name,
            path=skill_source_dir,
            url=spec.url_or_path if spec.kind == "git" else None,
            commit=commit if spec.kind == "git" else None,
        )
        installed = GlobalInstalledSkill(
            name=skill.name,
            resolved=resolved,
            install_path=install_link,
        )

        for agent in target_agents:
            link_path = global_agent_skill_dir(agent, skill.name, home)
            link_path.parent.mkdir(parents=True, exist_ok=True)
            _materialise_agent_link(link_path, install_link, adapter, mode, force=force)
            installed.fanned_out_to.append(agent)

        report.installed.append(installed)

    return report


def _replace_with_symlink(link: Path, target: Path, *, force: bool) -> None:
    """Create `link -> target`. Replace existing managed entries; refuse
    to clobber unmanaged content unless `force=True`."""
    link.parent.mkdir(parents=True, exist_ok=True)

    if link.is_symlink():
        link.unlink()
    elif link.exists():
        if not force:
            raise InstallConflict(
                f"refusing to overwrite existing path at {link} "
                f"(use --yes / -y to replace)"
            )
        if link.is_dir():
            shutil.rmtree(link)
        else:
            link.unlink()

    try:
        link.symlink_to(target)
    except OSError as exc:
        raise InstallSystemError(f"could not create symlink {link} -> {target}: {exc}") from exc


def _materialise_agent_link(
    link: Path,
    source: Path,
    adapter: IdentityAdapter,
    mode: InstallMode,
    *,
    force: bool,
) -> None:
    """Create the `~/.<agent>/skills/<name>` entry pointing at `source`.

    Symlink mode delegates to the adapter (so behaviour matches project
    fan-out); copy/hardlink modes also go through the adapter.
    """
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        if not force:
            raise InstallConflict(
                f"refusing to overwrite existing path at {link} "
                f"(use --yes / -y to replace)"
            )
        if link.is_dir():
            shutil.rmtree(link)
        else:
            link.unlink()

    try:
        adapter.adapt(
            skill_name=source.name,
            source_dir=source,
            target_dir=link,
            mode=mode,
        )
    except OSError as exc:
        with suppress(OSError):
            if link.is_symlink() or link.exists():
                if link.is_dir() and not link.is_symlink():
                    shutil.rmtree(link, ignore_errors=True)
                else:
                    link.unlink(missing_ok=True)
        raise InstallSystemError(
            f"could not materialise global fan-out at {link}: {exc}"
        ) from exc


def uninstall_global(
    skill_name: str,
    *,
    agents: Iterable[str] | None = None,
    home: Path | None = None,
) -> list[Path]:
    """Remove `~/.skillpod/skills/<name>` and matching fan-out entries.

    Returns the list of paths that were actually removed.
    """
    target_agents = list(agents) if agents is not None else list(DEFAULT_GLOBAL_AGENTS)
    removed: list[Path] = []

    install_link = global_skill_dir(skill_name, home)
    if install_link.is_symlink() or install_link.exists():
        if install_link.is_symlink() or install_link.is_file():
            install_link.unlink()
        else:
            shutil.rmtree(install_link)
        removed.append(install_link)

    for agent in target_agents:
        link = global_agent_skill_dir(agent, skill_name, home)
        if link.is_symlink():
            link.unlink()
            removed.append(link)
        elif link.exists():
            # Don't touch unmanaged content during uninstall.
            logger.debug("skipping unmanaged path during uninstall: %s", link)
    return removed


__all__ = [
    "DEFAULT_GLOBAL_AGENTS",
    "GlobalInstallReport",
    "GlobalInstalledSkill",
    "install_global",
    "uninstall_global",
]


# Silence the unused-import lint for `os` (kept for potential future use).
_ = os
