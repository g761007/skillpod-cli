"""skillpod profile save — snapshot the current global skills into a profile.

Scans the skills currently fanned out to agents, recovers each one's source
best-effort (so the profile is portable), and writes it to
``~/.skillpod/profiles/<name>.yml``.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer.paths import global_profile_path
from skillpod.profile.errors import ProfileError
from skillpod.profile.snapshot import snapshot_current_global, write_global_profile_body


def run(
    name: str,
    *,
    description: str | None = None,
    overwrite: bool = False,
    json_output: bool = False,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        dest = global_profile_path(name, home)
        if dest.is_file() and not overwrite:
            raise ProfileError(
                f"global profile '{name}' already exists; pass --yes to overwrite"
            )

        body = snapshot_current_global(home, name=name, description=description)
        write_global_profile_body(name, body, home)

        with_source = sum(1 for s in body.skills if s.source is not None)
        without = len(body.skills) - with_source
        emit(
            {
                "ok": True,
                "profile": name,
                "path": str(dest),
                "skills": len(body.skills),
                "with_source": with_source,
                "name_only": without,
            },
            json_output=json_output,
            human=(
                f"Saved global profile '{name}' ({len(body.skills)} skills: "
                f"{with_source} with recovered source, {without} name-only) → {dest}"
            ),
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
