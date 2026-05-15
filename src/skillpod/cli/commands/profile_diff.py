"""skillpod profile diff — show skill differences between two profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.skillset.compose import compose_effective_skillset


def run(
    name_a: str,
    name_b: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        manifest = load(manifest_path)

        skillset_a = compose_effective_skillset(
            manifest,
            project_root,
            profile_name=name_a,
            home=home,
        )
        skillset_b = compose_effective_skillset(
            manifest,
            project_root,
            profile_name=name_b,
            home=home,
        )

        skills_a = {s.name for s in skillset_a.skills}
        skills_b = {s.name for s in skillset_b.skills}

        added = sorted(skills_b - skills_a)
        removed = sorted(skills_a - skills_b)
        common = sorted(skills_a & skills_b)

        payload: dict[str, Any] = {
            "added": added,
            "removed": removed,
            "common": common,
        }

        lines: list[str] = []
        for s in added:
            lines.append(f"+ {s}")
        for s in removed:
            lines.append(f"- {s}")
        for s in common:
            lines.append(f"  {s}")

        emit(payload, json_output=json_output, human="\n".join(lines) if lines else "(no skills)")

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
