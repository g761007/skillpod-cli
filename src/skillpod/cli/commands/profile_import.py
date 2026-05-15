"""skillpod profile import — import a profile from a YAML export file."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.profile.errors import ProfileError

_VALID_IMPORT_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def run(
    file: Path,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    is_global: bool = False,
    rename: str | None = None,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        try:
            raw = yaml.safe_load(file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProfileError(f"cannot read export file: {exc}") from exc

        if not isinstance(raw, dict):
            raise ProfileError("invalid export file: top level must be a mapping")

        if "skillpod_profile_export" not in raw:
            raise ProfileError(
                "invalid export file: missing 'skillpod_profile_export' header"
            )

        profile_data = raw.get("profile")
        if not isinstance(profile_data, dict):
            raise ProfileError("invalid export file: missing 'profile' section")

        name = rename if rename is not None else profile_data.get("name", "")
        if not name:
            raise ProfileError("profile name is empty; use --rename to specify a name")

        if not _VALID_IMPORT_NAME.match(name):
            raise ProfileError(
                f"profile name '{name}' is invalid; "
                "use only lowercase letters, digits, and hyphens (no '+' allowed)"
            )

        profile_body: dict[str, object] = {}
        if profile_data.get("type") is not None:
            profile_body["type"] = profile_data["type"]
        agents = profile_data.get("agents") or []
        if agents:
            profile_body["agents"] = list(agents)
        skills = profile_data.get("skills") or []
        if skills:
            profile_body["skills"] = list(skills)

        export_content: dict[str, object] = {"version": 1, "profile": profile_body}

        if is_global:
            _home = home or Path.home()
            dest = _home / ".skillpod" / "profiles" / f"{name}.yml"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                yaml.safe_dump(
                    export_content,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            scope = "global"
        else:
            imported_dir = project_root / ".skillpod" / "imported"
            imported_dir.mkdir(parents=True, exist_ok=True)
            dest = imported_dir / f"{name}.yml"
            dest.write_text(
                yaml.safe_dump(
                    export_content,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            scope = "project"

        emit(
            {"imported": True, "name": name, "scope": scope},
            json_output=json_output,
            human=f"imported profile '{name}' to {scope}",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
