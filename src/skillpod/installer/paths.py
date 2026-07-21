"""Project-relative paths used by the installer."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_INSTALL_ROOT = ".skillpod/skills"
GLOBAL_INSTALL_ROOT_REL = ".skillpod/skills"
GLOBAL_PROFILES_REL = ".skillpod/profiles"
INSTALL_RECORD_REL = ".skillpod/installed.yml"


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


def global_profiles_root(home: Path | None = None) -> Path:
    """Return `~/.skillpod/profiles/` (or `<home>/.skillpod/profiles` for tests)."""
    base = (home or Path.home()).expanduser()
    return base / GLOBAL_PROFILES_REL


def global_profile_path(name: str, home: Path | None = None) -> Path:
    """Return `~/.skillpod/profiles/<name>.yml`."""
    return global_profiles_root(home) / f"{name}.yml"


def global_skill_dir(skill_name: str, home: Path | None = None) -> Path:
    """Return `~/.skillpod/skills/<skill_name>`."""
    return global_install_root(home) / skill_name


def project_record_path(project_root: Path) -> Path:
    """Return `<project_root>/.skillpod/installed.yml`.

    Lives under `.skillpod/`, which `skillpod init` already gitignores — the
    record describes one machine and must never be committed.
    """
    return project_root / INSTALL_RECORD_REL


def global_record_path(home: Path | None = None) -> Path:
    """Return `~/.skillpod/installed.yml`."""
    base = (home or Path.home()).expanduser()
    return base / INSTALL_RECORD_REL


def global_agent_skill_dir(agent: str, skill_name: str, home: Path | None = None) -> Path:
    """Return `~/.<agent>/skills/<skill_name>`."""
    base = (home or Path.home()).expanduser()
    return base / f".{agent}" / "skills" / skill_name


def is_managed_global_fanout(
    link_path: Path, skill_name: str, home: Path | None = None
) -> bool:
    """True if `link_path` is a symlink whose immediate target points to
    ``~/.skillpod/skills/<skill_name>``.

    Handles Windows ``\\\\?\\`` extended-length path prefix and macOS ``/private``
    aliasing the same way as :func:`is_managed_fanout`.
    """
    if not link_path.is_symlink():
        return False
    raw_str = os.readlink(link_path)
    if raw_str.startswith("\\\\?\\"):
        raw_str = raw_str[4:]
    raw = Path(raw_str)
    immediate = raw if raw.is_absolute() else (link_path.parent / raw)
    try:
        parent_canonical = immediate.parent.resolve(strict=False)
    except OSError:
        return False
    leaf_full = parent_canonical / immediate.name
    target = global_skill_dir(skill_name, home)
    try:
        target_canonical = target.parent.resolve(strict=False) / target.name
    except OSError:
        return False
    return leaf_full == target_canonical


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
    raw_str = os.readlink(link_path)
    # Windows extended-length path prefix (\\?\) breaks relative_to comparison; strip it.
    if raw_str.startswith("\\\\?\\"):
        raw_str = raw_str[4:]
    raw = Path(raw_str)
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
    "GLOBAL_PROFILES_REL",
    "INSTALL_RECORD_REL",
    "PROJECT_INSTALL_ROOT",
    "agent_skill_dir",
    "global_agent_skill_dir",
    "global_install_root",
    "global_profile_path",
    "global_profiles_root",
    "global_record_path",
    "global_skill_dir",
    "install_root",
    "is_managed_fanout",
    "is_managed_global_fanout",
    "project_record_path",
    "project_skill_dir",
]
