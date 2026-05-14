"""skillpod profile add — add a skill to a profile."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer.expand import flatten
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
            if skill_name in entry.skills:
                raise ProfileError(
                    f"skill '{skill_name}' already in global profile '{profile_name}'"
                )
            new_skills = [*entry.skills, skill_name]
            write_global_profile(
                profile_name,
                ProfileEntry(type=entry.type, agents=entry.agents, skills=new_skills),
                home,
            )
            scope = "global"
        else:
            manifest = load(manifest_path)
            flat_names = {s.name for s in flatten(manifest)}
            if skill_name not in flat_names:
                raise ProfileError(
                    f"skill '{skill_name}' is not declared in this project; "
                    f"add it to skillfile.yml first"
                )
            entry = get_project_profile(manifest, profile_name)
            if entry is None:
                raise ProfileError(f"project profile '{profile_name}' not found")
            if skill_name in entry.skills:
                raise ProfileError(
                    f"skill '{skill_name}' already in project profile '{profile_name}'"
                )
            new_skills = [*entry.skills, skill_name]
            update_project_profile_skills(profile_name, new_skills, manifest_path)
            scope = "project"

        emit(
            {"ok": True, "profile": profile_name, "skill": skill_name, "scope": scope},
            json_output=json_output,
            human=f"added '{skill_name}' to profile '{profile_name}' ({scope})",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
