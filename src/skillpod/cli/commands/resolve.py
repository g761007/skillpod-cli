"""skillpod resolve — show the effective skill set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.skillset.compose import compose_effective_skillset


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    profile_name: str | None,
    explain: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        manifest = load(manifest_path)
        effective = compose_effective_skillset(
            manifest, project_root, profile_name=profile_name, home=home
        )

        if json_output:
            payload: dict[str, Any] = {
                "profile": profile_name,
                "skills": [s.name for s in effective.skills],
            }
            if explain:
                payload["provenance"] = {
                    name: origin.value for name, origin in effective.provenance.items()
                }
            emit(payload, json_output=True)
            return

        if not effective.skills:
            emit(None, json_output=False, human="(no skills in effective set)")
            return

        if explain:
            name_w = max(len(s.name) for s in effective.skills)
            lines = [f"{'NAME':<{name_w}}  ORIGIN"]
            lines.append("-" * (name_w + 20))
            for s in effective.skills:
                origin = effective.provenance.get(s.name, "project")
                lines.append(f"{s.name:<{name_w}}  {origin}")
            emit(None, json_output=False, human="\n".join(lines))
        else:
            emit(
                None,
                json_output=False,
                human="\n".join(s.name for s in effective.skills),
            )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
