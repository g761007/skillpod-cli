"""skillpod profile apply — reconcile global skills to a global profile.

Activating a global profile materialises exactly its skills into the per-agent
global skill directories, downloading any missing skill from its inline source.
Without ``--yes`` the command only previews the reconciliation diff.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer.global_apply import ApplyPlan, execute_apply, plan_apply
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import load_global_profile_body
from skillpod.state.io import write_active_profile


def _format_plan(name: str, plan: ApplyPlan) -> str:
    lines = [f"Apply plan for global profile '{name}' (agents: {', '.join(plan.agents)}):"]
    if plan.to_download:
        lines.append(f"  download ({len(plan.to_download)}): "
                     + ", ".join(s.name for s in plan.to_download))
    if plan.to_link:
        lines.append(f"  link ({len(plan.to_link)}): " + ", ".join(plan.to_link))
    if plan.to_unlink:
        lines.append(f"  unlink ({len(plan.to_unlink)}): " + ", ".join(plan.to_unlink))
    if not plan.has_changes:
        lines.append("  (already in sync — nothing to do)")
    return "\n".join(lines)


def run(
    name: str,
    *,
    project_root: Path,
    yes: bool,
    json_output: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        body = load_global_profile_body(name, home)
        if body is None:
            raise ProfileError(
                f"global profile '{name}' not found in ~/.skillpod/profiles/"
            )

        plan = plan_apply(body, home=home)
        if plan.unresolved:
            raise ProfileError(
                "cannot apply: skills missing from ~/.skillpod/skills/ with no source "
                f"to download from: {', '.join(plan.unresolved)}"
            )

        plan_payload = {
            "to_download": [s.name for s in plan.to_download],
            "to_link": plan.to_link,
            "to_unlink": plan.to_unlink,
            "agents": plan.agents,
        }

        if not yes:
            emit(
                {"ok": True, "profile": name, "applied": False, "plan": plan_payload},
                json_output=json_output,
                human=_format_plan(name, plan)
                + ("\n\nRe-run with --yes to apply." if plan.has_changes else ""),
            )
            return

        # `--yes` only confirms execution; it must NOT silently overwrite
        # unmanaged data. A real (non-symlink) directory sitting at a fan-out
        # target raises InstallConflict so the user is told rather than having
        # their hand-placed content deleted.
        report = execute_apply(body, plan, force=False, home=home)
        write_active_profile(name, "global", project_root, home=home)

        emit(
            {
                "ok": True,
                "profile": name,
                "applied": True,
                "agents": report.agents,
                "downloaded": report.downloaded,
                "linked": report.linked,
                "unlinked": report.unlinked,
            },
            json_output=json_output,
            human=(
                f"Applied global profile '{name}'. "
                f"downloaded={len(report.downloaded)}, linked={len(report.linked)}, "
                f"unlinked={len(report.unlinked)} (agents: {', '.join(report.agents)})"
            ),
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
