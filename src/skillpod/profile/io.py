"""Read and write profile data from global files and project manifests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from skillpod.installer.paths import global_profile_path, global_profiles_root
from skillpod.manifest.models import ProfileEntry, Skillfile
from skillpod.profile.errors import ProfileError
from skillpod.profile.models import GlobalProfileBody, GlobalProfileFile

_VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")

# ---------------------------------------------------------------------------
# Global profile I/O  (~/.skillpod/profiles/<name>.yml)
# ---------------------------------------------------------------------------


def _load_profile_body(name: str, path: Path) -> GlobalProfileBody | None:
    """Load a GlobalProfileBody from a YAML file path; return None if absent."""
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"invalid YAML in profile '{name}': {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"profile '{name}': top level must be a mapping")
    try:
        f = GlobalProfileFile.model_validate(data)
    except Exception as exc:
        raise ProfileError(f"profile '{name}': {exc}") from exc
    return f.profile


def _load_profile_file(name: str, path: Path) -> ProfileEntry | None:
    """Load a name-only ProfileEntry from a YAML file path; None if not found."""
    body = _load_profile_body(name, path)
    if body is None:
        return None
    return GlobalProfileFile(profile=body).as_profile_entry()


def _resolve_global_paths(name: str, home: Path | None) -> list[Path]:
    """Return the candidate file paths for a global profile, canonical first."""
    _home = home or Path.home()
    canonical = _home / ".skillpod" / "profiles" / f"{name}.yml"
    paths = [canonical]
    managed = global_profile_path(name, home)
    if managed != canonical:
        paths.append(managed)
    return paths


def load_global_profile(name: str, home: Path | None = None) -> ProfileEntry | None:
    """Load a global profile by name; return None if the file does not exist.

    Checks both the canonical path (~/.skillpod/profiles/<name>.yml) and the
    legacy global_profile_path location. Returns a name-only ``ProfileEntry``
    for filter-mode callers; use :func:`load_global_profile_body` for the
    source-bearing form.
    """
    for path in _resolve_global_paths(name, home):
        result = _load_profile_file(name, path)
        if result is not None:
            return result
    return None


def load_global_profile_body(
    name: str, home: Path | None = None
) -> GlobalProfileBody | None:
    """Load the source-bearing body of a global profile, or None if absent."""
    for path in _resolve_global_paths(name, home):
        body = _load_profile_body(name, path)
        if body is not None:
            return body
    return None


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


def get_project_profile(
    manifest: Skillfile,
    name: str,
    *,
    project_root: Path | None = None,
) -> ProfileEntry | None:
    """Return the named project profile or None.

    Also checks `.skillpod/imported/<name>.yml` when ``project_root`` is provided,
    which is where ``profile import`` writes sidecar profile files.
    """
    entry = manifest.profiles.get(name)
    if entry is not None:
        return entry
    if project_root is not None:
        imported_path = project_root / ".skillpod" / "imported" / f"{name}.yml"
        imported = _load_profile_file(name, imported_path)
        if imported is not None:
            return imported
    return None


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
    "load_global_profile_body",
    "update_project_profile_skills",
    "write_global_profile",
]
