"""skillpod profile show — display a profile's content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import ManifestError, load
from skillpod.manifest.models import ProfileEntry
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import get_project_profile, load_global_profile


def _entry_payload(name: str, entry: ProfileEntry, scope: str) -> dict[str, Any]:
    return {
        "name": name,
        "scope": scope,
        "type": entry.type,
        "agents": entry.agents,
        "skills": entry.skills,
    }


def _entry_human(name: str, entry: ProfileEntry, scope: str) -> str:
    lines = [
        f"name:    {name}",
        f"scope:   {scope}",
        f"type:    {entry.type or '-'}",
        f"agents:  {', '.join(entry.agents) or '-'}",
        f"skills ({len(entry.skills)}):",
    ]
    if entry.skills:
        lines.extend(f"  - {s}" for s in entry.skills)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    name: str,
    is_global: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        entry: ProfileEntry | None = None
        scope = "unknown"

        if not is_global:
            try:
                manifest = load(manifest_path)
                entry = get_project_profile(manifest, name)
                if entry is not None:
                    scope = "project"
            except ManifestError:
                pass

        if entry is None:
            entry = load_global_profile(name, home)
            if entry is not None:
                scope = "global"

        if entry is None:
            raise ProfileError(f"profile '{name}' not found")

        payload = _entry_payload(name, entry, scope)
        emit(payload, json_output=json_output, human=_entry_human(name, entry, scope))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
