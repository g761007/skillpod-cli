"""Load skillfile.yml from disk into a `Skillfile` model.

Responsibilities (per spec `manifest/spec.md`):
- Parse YAML (safe).
- Normalise shorthand skill entries (`- audit`) into the object form
  (`{name: audit}`).
- Reject malformed top-level shapes early with helpful errors.
- Reject unknown top-level keys (delegated to pydantic via `extra=forbid`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skillpod.manifest.models import Skillfile


class ManifestError(Exception):
    """Raised for any failure loading or validating skillfile.yml."""


def _normalise_skills(raw: Any, *, label: str = "skills") -> list[dict[str, Any]]:
    """Expand shorthand strings under a skill-entry list into object form."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ManifestError(f"`{label}:` must be a list, got {type(raw).__name__}")

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if isinstance(item, str):
            out.append({"name": item})
        elif isinstance(item, dict):
            out.append(item)
        else:
            raise ManifestError(
                f"`{label}[{idx}]`: expected string or mapping, got {type(item).__name__}"
            )
    return out


def _normalise_groups(raw: Any) -> dict[str, list[dict[str, Any]]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ManifestError(f"`groups:` must be a mapping, got {type(raw).__name__}")

    out: dict[str, list[dict[str, Any]]] = {}
    for name, members in raw.items():
        if not isinstance(name, str):
            raise ManifestError(f"`groups:` keys must be strings, got {type(name).__name__}")
        out[name] = _normalise_skills(members, label=f"groups.{name}")
    return out


def _normalise_agents(raw: Any) -> list[dict[str, Any]]:
    """Normalise the ``agents:`` list to object form.

    Accepts:
    - ``"claude"``                          → ``{"name": "claude"}``
    - ``{"name": "claude", "adapter": …}``  → kept as-is
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ManifestError(f"`agents:` must be a list, got {type(raw).__name__}")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if isinstance(item, str):
            out.append({"name": item})
        elif isinstance(item, dict):
            out.append(item)
        else:
            raise ManifestError(
                f"`agents[{idx}]`: expected string or mapping, got {type(item).__name__}"
            )
    return out


def loads(text: str) -> Skillfile:
    """Parse manifest YAML text into a `Skillfile`."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"invalid YAML: {exc}") from exc

    if data is None:
        raise ManifestError("manifest is empty")
    if not isinstance(data, dict):
        raise ManifestError(
            f"manifest top level must be a mapping, got {type(data).__name__}"
        )

    if "skills" in data:
        data["skills"] = _normalise_skills(data["skills"])
    if "groups" in data:
        data["groups"] = _normalise_groups(data["groups"])
    if "agents" in data:
        data["agents"] = _normalise_agents(data["agents"])

    try:
        return Skillfile.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError or our own ValueError
        raise ManifestError(str(exc)) from exc


def load(path: str | Path) -> Skillfile:
    """Read manifest YAML from `path` and return the parsed model."""
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p}")
    return loads(p.read_text(encoding="utf-8"))


__all__ = ["ManifestError", "load", "loads"]
