"""skillpod profile remove — remove a skill from a profile."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.manifest.models import ProfileEntry
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import (
    get_project_profile,
    load_global_profile,
    update_project_profile_skills,
    write_global_profile,
)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    profile_name: str,
    skill_name: str,
    is_global: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        if is_global:
            entry = load_global_profile(profile_name, home)
            if entry is None:
                raise ProfileError(f"global profile '{profile_name}' not found")
            if skill_name not in entry.skills:
                raise ProfileError(
                    f"skill '{skill_name}' not in global profile '{profile_name}'"
                )
            new_skills = [s for s in entry.skills if s != skill_name]
            write_global_profile(
                profile_name,
                ProfileEntry(type=entry.type, agents=entry.agents, skills=new_skills),
                home,
            )
            scope = "global"
        else:
            manifest = load(manifest_path)
            entry = get_project_profile(manifest, profile_name)
            if entry is None:
                raise ProfileError(f"project profile '{profile_name}' not found")
            if skill_name not in entry.skills:
                raise ProfileError(
                    f"skill '{skill_name}' not in project profile '{profile_name}'"
                )
            new_skills = [s for s in entry.skills if s != skill_name]
            update_project_profile_skills(profile_name, new_skills, manifest_path)
            scope = "project"

        emit(
            {"ok": True, "profile": profile_name, "skill": skill_name, "scope": scope},
            json_output=json_output,
            human=f"removed '{skill_name}' from profile '{profile_name}' ({scope})",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
