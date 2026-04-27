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


def _normalise_skills(raw: Any) -> list[dict[str, Any]]:
    """Expand shorthand strings under `skills:` into object form."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ManifestError(f"`skills:` must be a list, got {type(raw).__name__}")

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if isinstance(item, str):
            out.append({"name": item})
        elif isinstance(item, dict):
            out.append(item)
        else:
            raise ManifestError(
                f"`skills[{idx}]`: expected string or mapping, got {type(item).__name__}"
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
