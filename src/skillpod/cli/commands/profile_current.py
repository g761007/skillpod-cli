"""skillpod profile current — show the active profile and its scope."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.state.active import read_active_profile


def run(
    *,
    project_root: Path,
    json_output: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        name, scope = read_active_profile(project_root, home=home)
        if name is None:
            emit(
                {"active_profile": None, "scope": None},
                json_output=json_output,
                human="(none)",
            )
        else:
            emit(
                {"active_profile": name, "scope": scope},
                json_output=json_output,
                human=f"{name} (scope: {scope})",
            )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
