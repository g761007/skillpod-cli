"""skillpod profile export — export a profile to a self-contained YAML file."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import get_project_profile, load_global_profile


def run(
    name: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    out: Path | None = None,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        entry = None
        scope = "unknown"

        try:
            manifest = load(manifest_path)
            entry = get_project_profile(manifest, name)
            if entry is not None:
                scope = "project"
        except Exception:
            pass

        if entry is None:
            entry = load_global_profile(name, home)
            if entry is not None:
                scope = "global"

        if entry is None:
            raise ProfileError(f"profile '{name}' not found")

        exported_at = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload: dict[str, Any] = {
            "skillpod_profile_export": "1",
            "exported_at": exported_at,
            "source_scope": scope,
            "profile": {
                "name": name,
                "type": entry.type,
                "skills": list(entry.skills),
                "agents": list(entry.agents),
            },
        }

        if json_output:
            emit(payload, json_output=True)
            return

        yaml_text = yaml.safe_dump(
            payload, sort_keys=False, default_flow_style=False, allow_unicode=True
        )

        if out is not None:
            out.write_text(yaml_text, encoding="utf-8")
            emit(
                {"exported": True, "name": name, "path": str(out)},
                json_output=False,
                human=f"exported profile '{name}' to {out}",
            )
        else:
            import typer
            typer.echo(yaml_text, nl=False)

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
