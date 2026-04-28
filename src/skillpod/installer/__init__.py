"""Installer capability: orchestrator + fan-out (symlink/copy/hardlink)."""

from skillpod.installer.adapter import Adapter, InstallMode
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.installer.adapter_registry import get_adapter, register_adapter, reset_registry
from skillpod.installer.errors import (
    AdapterImportError,
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
    materialise_fanout,
    materialise_install_root,
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
    "Adapter",
    "AdapterImportError",
    "FrozenDriftError",
    "IdentityAdapter",
    "InstallConflict",
    "InstallError",
    "InstallMode",
    "InstallReport",
    "InstallSystemError",
    "InstallUserError",
    "InstalledSkill",
    "agent_skill_dir",
    "create_install_root_symlink",  # deprecated alias for materialise_install_root
    "create_managed_fanout_symlink",
    "discover_user_skills",
    "flatten",
    "get_adapter",
    "install",
    "install_root",
    "is_managed_fanout",
    "materialise_fanout",
    "materialise_install_root",
    "project_skill_dir",
    "register_adapter",
    "reset_registry",
    "resolve_skill",
    "resolve_user_skill",
    "rollback_on_failure",
    "uninstall",
    "user_skills_root",
]
