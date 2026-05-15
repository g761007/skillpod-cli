"""Write and clear the active profile state for a given scope."""

from __future__ import annotations

from pathlib import Path

from skillpod.state.active import global_active_profile_path, project_active_profile_path


def write_active_profile(
    name: str,
    scope: str,
    project_root: Path,
    *,
    home: Path | None = None,
) -> None:
    """Persist `name` as the active profile for `scope` ('project' or 'global').

    For the 'session' scope callers print the env-var export line to stdout themselves.
    """
    if scope == "project":
        path = project_active_profile_path(project_root)
    elif scope == "global":
        path = global_active_profile_path(home)
    else:
        raise ValueError(f"unsupported scope: {scope!r}; use 'project', 'global', or 'session'")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")


def clear_active_profile(
    scope: str,
    project_root: Path,
    *,
    home: Path | None = None,
) -> bool:
    """Remove the active-profile state file for `scope`. Returns True if a file was removed."""
    if scope == "project":
        path = project_active_profile_path(project_root)
    elif scope == "global":
        path = global_active_profile_path(home)
    else:
        raise ValueError(f"unsupported scope: {scope!r}")
    if path.is_file():
        path.unlink()
        return True
    return False


__all__ = ["clear_active_profile", "write_active_profile"]
