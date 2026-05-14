"""skillpod profile list — list available profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import ManifestError, load
from skillpod.profile.io import list_global_profiles, list_project_profiles


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    global_only: bool,
    project_only: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        rows: list[dict[str, Any]] = []

        if not global_only:
            try:
                manifest = load(manifest_path)
                for pname in list_project_profiles(manifest):
                    entry = manifest.profiles[pname]
                    rows.append(
                        {
                            "name": pname,
                            "scope": "project",
                            "type": entry.type,
                            "skills": entry.skills,
                            "agents": entry.agents,
                        }
                    )
            except ManifestError:
                pass  # no project manifest — show global only

        if not project_only:
            for pname in list_global_profiles(home):
                rows.append({"name": pname, "scope": "global", "type": None, "skills": [], "agents": []})

        if json_output:
            emit(rows, json_output=True)
            return

        if not rows:
            emit(None, json_output=False, human="no profiles found")
            return

        name_w = max(len(r["name"]) for r in rows)
        lines = [f"{'NAME':<{name_w}}  SCOPE    TYPE"]
        lines.append("-" * (name_w + 20))
        for r in rows:
            lines.append(
                f"{r['name']:<{name_w}}  {r['scope']:<7}  {r['type'] or '-'}"
            )
        emit(None, json_output=False, human="\n".join(lines))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
