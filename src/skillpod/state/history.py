"""Single-level undo history for the global skill set.

Before a global ``switch`` changes the materialised skills, the *current* set is
snapshotted here so ``switch --back`` can restore it. Only the immediately
previous state is kept (single level); each save overwrites the last.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skillpod.profile.models import GlobalProfileBody
from skillpod.profile.snapshot import serialize_profile_body

_HISTORY_REL = ".skillpod/history/previous.yml"


def previous_global_path(home: Path | None = None) -> Path:
    base = (home or Path.home()).expanduser()
    return base / _HISTORY_REL


def save_previous_global(
    body: GlobalProfileBody,
    active_profile: str | None,
    home: Path | None = None,
) -> Path:
    """Persist ``body`` (and the active-profile name) as the undo point."""
    path = previous_global_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": 1,
        "active_profile": active_profile,
        "profile": serialize_profile_body(body)["profile"],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_previous_global(
    home: Path | None = None,
) -> tuple[GlobalProfileBody, str | None] | None:
    """Return ``(body, active_profile)`` from the undo point, or None if absent."""
    path = previous_global_path(home)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profile"), dict):
        return None
    body = GlobalProfileBody.model_validate(data["profile"])
    active = data.get("active_profile")
    return body, (active if isinstance(active, str) else None)


__all__ = [
    "load_previous_global",
    "previous_global_path",
    "save_previous_global",
]
