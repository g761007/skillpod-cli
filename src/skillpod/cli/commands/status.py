"""skillpod status — show project and profile state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.manifest.loader import ManifestError, load
from skillpod.profile.io import list_global_profiles, list_project_profiles
from skillpod.skillset.compose import compose_effective_skillset


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    profile_name: str | None,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        try:
            manifest = load(manifest_path)
            manifest_ok = True
        except ManifestError as exc:
            manifest_ok = False
            manifest_err = str(exc)

        global_profiles = list_global_profiles(home)

        if not manifest_ok:
            payload: dict[str, Any] = {
                "project": None,
                "manifest_error": manifest_err,
                "profiles": {"global": global_profiles},
            }
            human_lines = [
                f"manifest: not found ({manifest_path})",
                f"global profiles: {', '.join(global_profiles) or '(none)'}",
            ]
            emit(payload, json_output=json_output, human="\n".join(human_lines))
            return

        project_name = project_root.name
        project_profiles = list_project_profiles(manifest)

        payload = {
            "project": project_name,
            "manifest": str(manifest_path),
            "skills": len(manifest.skills),
            "profiles": {
                "project": project_profiles,
                "global": global_profiles,
            },
        }

        human_lines = [
            f"project:   {project_name}",
            f"manifest:  {manifest_path}",
            f"skills:    {len(manifest.skills)}",
            "",
            "profiles:",
        ]
        for p in project_profiles:
            human_lines.append(f"  {p}  [project]")
        for p in global_profiles:
            human_lines.append(f"  {p}  [global]")
        if not project_profiles and not global_profiles:
            human_lines.append("  (none)")

        if profile_name is not None:
            effective = compose_effective_skillset(
                manifest, project_root, profile_name=profile_name, home=home
            )
            payload["active_profile"] = profile_name
            payload["effective_skills"] = [s.name for s in effective.skills]
            human_lines += [
                "",
                f"active profile: {profile_name}",
                f"effective skills ({len(effective.skills)}):",
            ]
            human_lines.extend(f"  {s.name}" for s in effective.skills)
        else:
            human_lines += ["", "(pass --profile NAME to show effective skills)"]

        emit(payload, json_output=json_output, human="\n".join(human_lines))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
