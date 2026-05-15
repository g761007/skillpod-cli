"""Read the active profile from state layers (session > project > global)."""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "SKILLPOD_ACTIVE_PROFILE"
_PROJECT_STATE_REL = ".skillpod/active-profile"
_GLOBAL_STATE_REL = ".skillpod/active-profile"


def read_active_profile(
    project_root: Path,
    *,
    home: Path | None = None,
) -> tuple[str | None, str | None]:
    """Return (profile_name, scope) or (None, None) if no active profile is set.

    Priority: session env var > project file > global file.
    """
    env_val = os.environ.get(ENV_VAR, "").strip()
    if env_val:
        return (env_val, "session")

    project_file = project_root / _PROJECT_STATE_REL
    if project_file.is_file():
        name = project_file.read_text(encoding="utf-8").strip()
        if name:
            return (name, "project")

    base = (home or Path.home()).expanduser()
    global_file = base / _GLOBAL_STATE_REL
    if global_file.is_file():
        name = global_file.read_text(encoding="utf-8").strip()
        if name:
            return (name, "global")

    return (None, None)


def project_active_profile_path(project_root: Path) -> Path:
    return project_root / _PROJECT_STATE_REL


def global_active_profile_path(home: Path | None = None) -> Path:
    base = (home or Path.home()).expanduser()
    return base / _GLOBAL_STATE_REL


__all__ = [
    "ENV_VAR",
    "global_active_profile_path",
    "project_active_profile_path",
    "read_active_profile",
]
