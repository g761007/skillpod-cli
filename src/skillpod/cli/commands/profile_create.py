"""skillpod profile create — create a new empty profile."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.manifest.models import ProfileEntry
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import (
    create_project_profile,
    load_global_profile,
    write_global_profile,
)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    name: str,
    is_global: bool,
    profile_type: str | None,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        entry = ProfileEntry(type=profile_type)

        if is_global:
            if load_global_profile(name, home) is not None:
                raise ProfileError(f"global profile '{name}' already exists")
            write_global_profile(name, entry, home)
            scope = "global"
        else:
            load(manifest_path)  # validate manifest is present and valid
            create_project_profile(name, entry, manifest_path)
            scope = "project"

        emit(
            {"ok": True, "name": name, "scope": scope},
            json_output=json_output,
            human=f"profile '{name}' created ({scope})",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
