"""Installer capability: orchestrator + symlink fan-out."""

from skillpod.installer.errors import (
    FrozenDriftError,
    InstallConflict,
    InstallError,
    InstallSystemError,
    InstallUserError,
)
from skillpod.installer.fanout import (
    create_install_root_symlink,
    create_managed_fanout_symlink,
    rollback_on_failure,
)
from skillpod.installer.paths import (
    PROJECT_INSTALL_ROOT,
    agent_skill_dir,
    install_root,
    is_managed_fanout,
    project_skill_dir,
)
from skillpod.installer.pipeline import (
    InstalledSkill,
    InstallReport,
    install,
    uninstall,
)
from skillpod.installer.resolve import resolve_skill

__all__ = [
    "PROJECT_INSTALL_ROOT",
    "FrozenDriftError",
    "InstallConflict",
    "InstallError",
    "InstallReport",
    "InstallSystemError",
    "InstallUserError",
    "InstalledSkill",
    "agent_skill_dir",
    "create_install_root_symlink",
    "create_managed_fanout_symlink",
    "install",
    "install_root",
    "is_managed_fanout",
    "project_skill_dir",
    "resolve_skill",
    "rollback_on_failure",
    "uninstall",
]
