"""skillpod profile use — alias for 'switch', mounted on profile_app."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli.commands.switch import run as switch_run


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
    switch_run(
        name,
        scope,
        project_root=project_root,
        manifest_path=manifest_path,
        json_output=json_output,
        yes_global=yes_global,
        home=home,
    )


__all__ = ["run"]
