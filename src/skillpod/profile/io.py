"""Read and write profile data from global files and project manifests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from skillpod.installer.paths import global_profile_path, global_profiles_root
from skillpod.manifest.models import ProfileEntry, Skillfile
from skillpod.profile.errors import ProfileError
from skillpod.profile.models import GlobalProfileFile

_VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")

# ---------------------------------------------------------------------------
# Global profile I/O  (~/.skillpod/profiles/<name>.yml)
# ---------------------------------------------------------------------------


def load_global_profile(name: str, home: Path | None = None) -> ProfileEntry | None:
    """Load a global profile by name; return None if the file does not exist."""
    path = global_profile_path(name, home)
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"invalid YAML in global profile '{name}': {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"global profile '{name}': top level must be a mapping")
    try:
        f = GlobalProfileFile.model_validate(data)
    except Exception as exc:
        raise ProfileError(f"global profile '{name}': {exc}") from exc
    return f.profile


def _validate_name(name: str) -> None:
    if not _VALID_NAME.match(name):
        raise ProfileError(
            f"profile name '{name}' is invalid; "
            "use only letters, digits, hyphens, and underscores"
        )


def write_global_profile(
    name: str, profile: ProfileEntry, home: Path | None = None
) -> None:
    """Serialise `profile` to `~/.skillpod/profiles/<name>.yml`."""
    _validate_name(name)
    path = global_profile_path(name, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {}
    if profile.type is not None:
        body["type"] = profile.type
    if profile.agents:
        body["agents"] = list(profile.agents)
    if profile.skills:
        body["skills"] = list(profile.skills)
    data: dict[str, Any] = {"version": 1, "profile": body}
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def list_global_profiles(home: Path | None = None) -> list[str]:
    """Return sorted names of all global profiles."""
    root = global_profiles_root(home)
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.glob("*.yml"))


# ---------------------------------------------------------------------------
# Project profile I/O  (skillfile.yml `profiles:` block)
# ---------------------------------------------------------------------------


def get_project_profile(manifest: Skillfile, name: str) -> ProfileEntry | None:
    """Return the named project profile or None."""
    return manifest.profiles.get(name)


def list_project_profiles(manifest: Skillfile) -> list[str]:
    """Return sorted names of all project profiles."""
    return sorted(manifest.profiles)


def create_project_profile(
    name: str, profile: ProfileEntry, manifest_path: Path
) -> None:
    """Add `profile` under `profiles.<name>` in the manifest YAML.

    Raises ProfileError if the profile already exists.
    """
    raw: dict[str, Any] = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    profiles: dict[str, Any] = raw.get("profiles") or {}
    if name in profiles:
        raise ProfileError(f"profile '{name}' already exists in project")
    body: dict[str, Any] = {}
    if profile.type is not None:
        body["type"] = profile.type
    if profile.agents:
        body["agents"] = list(profile.agents)
    if profile.skills:
        body["skills"] = list(profile.skills)
    profiles[name] = body
    raw["profiles"] = profiles
    manifest_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def update_project_profile_skills(
    name: str, skills: list[str], manifest_path: Path
) -> None:
    """Overwrite the `skills:` list for project profile `name`."""
    raw: dict[str, Any] = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    profiles: dict[str, Any] = raw.get("profiles") or {}
    if name not in profiles:
        raise ProfileError(f"profile '{name}' not found in project")
    if profiles[name] is None:
        profiles[name] = {}
    profiles[name]["skills"] = skills
    raw["profiles"] = profiles
    manifest_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


__all__ = [
    "create_project_profile",
    "get_project_profile",
    "list_global_profiles",
    "list_project_profiles",
    "load_global_profile",
    "update_project_profile_skills",
    "write_global_profile",
]
