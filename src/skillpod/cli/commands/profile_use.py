"""skillpod profile use — deprecated alias for `skillpod switch`.

Kept working, but no longer the documented spelling. Three commands used to
mean "activate this profile" — `switch`, `profile use`, and `shell` — and only
`shell` does something genuinely different (it spawns a sub-shell). Two names
for one action is a cost paid by every reader of the docs.
"""

from __future__ import annotations

from pathlib import Path

import typer

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
    # On stderr so it never contaminates `--json` consumers.
    typer.echo(
        "warning: `skillpod profile use` is deprecated — use `skillpod switch` instead.",
        err=True,
    )
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
