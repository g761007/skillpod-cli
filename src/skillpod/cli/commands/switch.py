"""skillpod switch — set the active profile for a scope."""

from __future__ import annotations

from pathlib import Path

import typer

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.profile.errors import ProfileError
from skillpod.state.active import ENV_VAR
from skillpod.state.io import write_active_profile


def run(
    name: str,
    scope: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    yes_global: bool = False,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        if scope == "session":
            export_line = f"export {ENV_VAR}={name}"
            typer.echo(export_line)
            typer.echo(
                f"hint: eval the above in your shell to activate profile '{name}'",
                err=True,
            )
            return

        if scope == "global" and manifest_path.is_file() and not yes_global:
            raise ProfileError(
                "refusing to write global active-profile from inside a project; "
                "pass --global to confirm"
            )

        write_active_profile(name, scope, project_root, home=home)
        emit(
            {"profile": name, "scope": scope},
            json_output=json_output,
            human=f"active profile set to '{name}' (scope: {scope})",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
