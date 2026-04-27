"""Read and write skillfile.lock with deterministic key ordering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skillpod.lockfile.models import LockedSkill, Lockfile


class LockfileError(Exception):
    """Raised on any failure reading or writing skillfile.lock."""


_FIELD_ORDER = ("source", "url", "commit", "sha256")


def _as_ordered_skill(skill: LockedSkill) -> dict[str, Any]:
    """Emit fields in a canonical order regardless of pydantic insertion order."""
    raw = skill.model_dump()
    return {key: raw[key] for key in _FIELD_ORDER}


def write(path: str | Path, model: Lockfile) -> None:
    """Persist `model` to `path` with sorted skill names and stable field order."""
    p = Path(path)
    payload: dict[str, Any] = {
        "version": model.version,
        "resolved": {
            name: _as_ordered_skill(model.resolved[name]) for name in sorted(model.resolved)
        },
    }
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    p.write_text(text, encoding="utf-8")


def read(path: str | Path) -> Lockfile:
    """Load `skillfile.lock` from disk, returning an empty Lockfile if absent."""
    p = Path(path)
    if not p.exists():
        return Lockfile()
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LockfileError(f"invalid YAML in {p}: {exc}") from exc

    if data is None:
        return Lockfile()
    if not isinstance(data, dict):
        raise LockfileError(f"lockfile top level must be a mapping, got {type(data).__name__}")

    try:
        return Lockfile.model_validate(data)
    except Exception as exc:
        raise LockfileError(str(exc)) from exc


__all__ = ["LockfileError", "read", "write"]
