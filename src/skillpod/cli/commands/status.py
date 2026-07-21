"""skillpod status — show project and profile state."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import typer

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.cli.commands.shell import ENV_DEPTH
from skillpod.manifest.loader import ManifestError, load
from skillpod.profile.io import list_global_profiles, list_project_profiles
from skillpod.skillset.compose import compose_effective_skillset
from skillpod.skillset.inventory import take_inventory
from skillpod.state.active import read_active_profile


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    profile_name: str | None,
    home: Path | None = None,
    ignore_global: bool = False,
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
        act = manifest.activation

        active_name, active_scope = read_active_profile(project_root, home=home)

        shell_depth_str = os.environ.get(ENV_DEPTH, "0")
        try:
            shell_depth = int(shell_depth_str)
        except ValueError:
            shell_depth = 0
        shell_active = shell_depth > 0
        shell_session_payload: dict[str, Any] = (
            {"active": True, "depth": shell_depth} if shell_active else {"active": False}
        )

        inv = take_inventory(manifest, project_root, home=home)

        payload = {
            "project": project_name,
            "manifest": str(manifest_path),
            "skills": len(manifest.skills),
            "inventory": {
                "recommended": inv.recommended,
                "satisfied": inv.satisfied,
                "from_global": inv.from_global,
                "from_project": inv.from_project,
                "from_user": inv.from_user,
                "missing": inv.missing,
                "broken": inv.broken,
                "detail": [
                    {"name": s.name, "state": str(s.state), "detail": s.detail}
                    for s in inv.skills
                ],
            },
            "activation": {
                "mode": act.mode,
                "inherit_global": act.inherit_global,
                "default_profile": act.default_profile,
            },
            "profiles": {
                "project": project_profiles,
                "global": global_profiles,
            },
            "active_profile": {"name": active_name, "scope": active_scope},
            "shell_session": shell_session_payload,
        }

        human_lines = [
            f"project:    {project_name}",
            f"manifest:   {manifest_path}",
            "",
            f"recommends: {inv.recommended} skill(s)",
        ]
        if inv.recommended:
            sources = ", ".join(
                part
                for part, count in (
                    (f"{inv.from_global} global", inv.from_global),
                    (f"{inv.from_project} project", inv.from_project),
                    (f"{inv.from_user} user", inv.from_user),
                )
                if count
            )
            human_lines.append(
                f"  satisfied: {inv.satisfied}" + (f"   ({sources})" if sources else "")
            )
            if inv.missing:
                human_lines.append(
                    f"  missing:   {len(inv.missing)}   → skillpod install"
                )
            if inv.broken:
                human_lines.append(
                    f"  broken:    {len(inv.broken)}   → skillpod doctor"
                )

        human_lines += [
            "",
            f"activation: {act.mode} / inherit_global={str(act.inherit_global).lower()}",
            "",
            "profiles:",
        ]
        for p in project_profiles:
            human_lines.append(f"  {p}  [project]")
        for p in global_profiles:
            human_lines.append(f"  {p}  [global]")
        if not project_profiles and not global_profiles:
            human_lines.append("  (none)")

        if active_name is not None:
            human_lines.append(f"\nactive profile: {active_name} (scope: {active_scope})")
        else:
            human_lines.append("\nactive profile: (none)")

        if shell_active:
            human_lines.append(f"shell session:  active (depth={shell_depth})")

        if profile_name is not None:
            effective = compose_effective_skillset(
                manifest,
                project_root,
                profile_name=profile_name,
                home=home,
                ignore_global=ignore_global,
            )
            for w in effective.warnings:
                typer.echo(f"warning: {w}", err=True)
            payload["profile_filter"] = profile_name
            payload["effective_skills"] = [s.name for s in effective.skills]
            human_lines += [
                "",
                f"effective skills for '{profile_name}' ({len(effective.skills)}):",
            ]
            human_lines.extend(f"  {s.name}" for s in effective.skills)
        else:
            human_lines.append("\n(pass --profile NAME to show effective skills)")

        emit(payload, json_output=json_output, human="\n".join(human_lines))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
