"""Project-relative paths used by the installer."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_INSTALL_ROOT = ".skillpod/skills"
GLOBAL_INSTALL_ROOT_REL = ".skillpod/skills"


def project_skill_dir(project_root: Path, skill_name: str) -> Path:
    """Return the canonical materialisation path for a skill in `project_root`."""
    return project_root / PROJECT_INSTALL_ROOT / skill_name


def agent_skill_dir(project_root: Path, agent: str, skill_name: str) -> Path:
    """Return the per-agent fan-out target path for a skill."""
    return project_root / f".{agent}" / "skills" / skill_name


def install_root(project_root: Path) -> Path:
    return project_root / PROJECT_INSTALL_ROOT


def global_install_root(home: Path | None = None) -> Path:
    """Return `~/.skillpod/skills/` (or `<home>/.skillpod/skills` for tests)."""
    base = (home or Path.home()).expanduser()
    return base / GLOBAL_INSTALL_ROOT_REL


def global_skill_dir(skill_name: str, home: Path | None = None) -> Path:
    """Return `~/.skillpod/skills/<skill_name>`."""
    return global_install_root(home) / skill_name


def global_agent_skill_dir(agent: str, skill_name: str, home: Path | None = None) -> Path:
    """Return `~/.<agent>/skills/<skill_name>`."""
    base = (home or Path.home()).expanduser()
    return base / f".{agent}" / "skills" / skill_name


def is_managed_fanout(link_path: Path, project_root: Path) -> bool:
    """True if `link_path` is a symlink whose *immediate* target points
    inside `<project_root>/.skillpod/skills/`.

    We check the immediate target (one hop) rather than fully resolving:
    fan-out symlinks point at `.skillpod/skills/<name>`, which is itself
    a symlink into the cache. A full resolve would land in the cache
    and incorrectly look "unmanaged". We only canonicalise the *parent*
    of the target (so macOS `/private` aliases line up) and leave the
    leaf segment literal.
    """
    if not link_path.is_symlink():
        return False
    raw = Path(os.readlink(link_path))
    immediate = raw if raw.is_absolute() else (link_path.parent / raw)
    try:
        parent_canonical = immediate.parent.resolve(strict=False)
    except OSError:
        return False
    leaf_full = parent_canonical / immediate.name
    root = install_root(project_root).resolve(strict=False)
    try:
        leaf_full.relative_to(root)
        return True
    except ValueError:
        return False


__all__ = [
    "GLOBAL_INSTALL_ROOT_REL",
    "PROJECT_INSTALL_ROOT",
    "agent_skill_dir",
    "global_agent_skill_dir",
    "global_install_root",
    "global_skill_dir",
    "install_root",
    "is_managed_fanout",
    "project_skill_dir",
]
