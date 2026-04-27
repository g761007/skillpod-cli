"""Installer capability: orchestrator + symlink fan-out."""

from skillpod.installer.errors import (
    FrozenDriftError,
    InstallConflict,
    InstallError,
    InstallSystemError,
    InstallUserError,
)
from skillpod.installer.expand import flatten
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
from skillpod.installer.user_skills import (
    USER_SKILLS_DIR,
    discover_user_skills,
    resolve_user_skill,
    user_skills_root,
)

__all__ = [
    "PROJECT_INSTALL_ROOT",
    "USER_SKILLS_DIR",
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
    "discover_user_skills",
    "flatten",
    "install",
    "install_root",
    "is_managed_fanout",
    "project_skill_dir",
    "resolve_skill",
    "resolve_user_skill",
    "rollback_on_failure",
    "uninstall",
    "user_skills_root",
]
