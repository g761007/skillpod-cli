"""Read and write `installed.yml` with deterministic ordering.

Deliberately shaped like the lockfile I/O it replaces,
but a missing file is unremarkable here: a record is written *after* an
install, so its absence simply means nothing has been installed yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skillpod.record.models import InstallRecord, SkillRecord


class RecordError(Exception):
    """Raised on any failure reading or writing an install record."""


_FIELD_ORDER = ("kind", "source", "ref", "commit", "subpath", "sha256")


def _as_ordered_skill(skill: SkillRecord) -> dict[str, Any]:
    """Emit fields in a canonical order, dropping unset ones.

    Omitting ``None`` keeps the file readable: an `unknown` entry is a bare
    ``kind: unknown`` rather than five null lines.
    """
    raw = skill.model_dump()
    return {key: raw[key] for key in _FIELD_ORDER if raw[key] is not None}


def write(path: str | Path, model: InstallRecord) -> None:
    """Persist `model` to `path` with sorted skill names and stable fields."""
    p = Path(path)
    payload: dict[str, Any] = {
        "version": model.version,
        "installed": {
            name: _as_ordered_skill(model.installed[name])
            for name in sorted(model.installed)
        },
    }
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise RecordError(f"could not write install record {p}: {exc}") from exc


def read(path: str | Path) -> InstallRecord:
    """Load an install record, returning an empty one if absent."""
    p = Path(path)
    if not p.exists():
        return InstallRecord()
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RecordError(f"invalid YAML in {p}: {exc}") from exc
    except OSError as exc:
        raise RecordError(f"could not read install record {p}: {exc}") from exc

    if data is None:
        return InstallRecord()
    if not isinstance(data, dict):
        raise RecordError(
            f"install record top level must be a mapping, got {type(data).__name__}"
        )

    try:
        return InstallRecord.model_validate(data)
    except Exception as exc:
        raise RecordError(str(exc)) from exc


__all__ = ["RecordError", "read", "write"]
