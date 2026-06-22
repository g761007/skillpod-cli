"""skillpod switch — set the active profile for a scope.

For ``--scope global`` this *materialises* the profile: it reconciles the global
per-agent skill directories to match it (downloading missing skills), records it
as the active global profile, and snapshots the previous set for ``--back``.
Project and session scopes remain lightweight (pointer / env export).
"""

from __future__ import annotations

from pathlib import Path

import typer

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer.global_apply import (
    ApplyPlan,
    ApplyReport,
    execute_apply,
    plan_apply,
)
from skillpod.installer.global_install import DEFAULT_GLOBAL_AGENTS
from skillpod.profile.errors import ProfileError
from skillpod.profile.fetch import resolve_profile_target
from skillpod.profile.models import GlobalProfileBody
from skillpod.profile.snapshot import current_global_agents, snapshot_current_global
from skillpod.state.active import ENV_VAR, global_active_profile_path
from skillpod.state.history import load_previous_global, save_previous_global
from skillpod.state.io import clear_active_profile, write_active_profile


def _format_plan(label: str, plan: ApplyPlan) -> str:
    lines = [f"Global skills for {label} (agents: {', '.join(plan.agents) or '<none>'}):"]
    if plan.to_download:
        lines.append("  download: " + ", ".join(s.name for s in plan.to_download))
    if plan.to_link:
        lines.append("  link: " + ", ".join(plan.to_link))
    if plan.to_unlink:
        lines.append("  unlink: " + ", ".join(plan.to_unlink))
    if plan.unresolved:
        lines.append("  skip (no source): " + ", ".join(plan.unresolved))
    if not plan.has_changes:
        lines.append("  (already in sync — nothing to do)")
    return "\n".join(lines)


def _current_global_active(home: Path | None) -> str | None:
    path = global_active_profile_path(home)
    if path.is_file():
        name = path.read_text(encoding="utf-8").strip()
        return name or None
    return None


def _emit_report(label: str, report: ApplyReport, json_output: bool) -> None:
    emit(
        {
            "ok": True,
            "profile": label,
            "applied": True,
            "agents": report.agents,
            "downloaded": report.downloaded,
            "linked": report.linked,
            "unlinked": report.unlinked,
            "skipped": report.skipped,
        },
        json_output=json_output,
        human=(
            f"Switched global skills to '{label}'. "
            f"downloaded={len(report.downloaded)}, linked={len(report.linked)}, "
            f"unlinked={len(report.unlinked)}, skipped={len(report.skipped)}"
        ),
    )


def _apply_global(
    label: str,
    body: GlobalProfileBody,
    new_active: str | None,
    *,
    agents: list[str] | None,
    project_root: Path,
    home: Path | None,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Reconcile global skills to ``body``; snapshot the current set for --back."""
    plan = plan_apply(body, agents=agents, home=home)
    if dry_run:
        emit(
            {"ok": True, "profile": label, "applied": False,
             "plan": {"to_download": [s.name for s in plan.to_download],
                      "to_link": plan.to_link, "to_unlink": plan.to_unlink,
                      "skipped": plan.unresolved, "agents": plan.agents}},
            json_output=json_output,
            human=_format_plan(label, plan)
            + ("\n\nDrop --dry-run to apply." if plan.has_changes else ""),
        )
        return

    # Snapshot the current global set so `switch --back` can restore it,
    # recording the agents it was actually on (internal state, not the profile).
    current = snapshot_current_global(home)
    save_previous_global(
        current, _current_global_active(home), current_global_agents(home), home
    )

    report = execute_apply(body, plan, force=False, home=home)
    if new_active is not None:
        write_active_profile(new_active, "global", project_root, home=home)
    else:
        clear_active_profile("global", project_root, home=home)
    _emit_report(label, report, json_output)


def run(
    name: str,
    scope: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    yes_global: bool = False,
    dry_run: bool = False,
    back: bool = False,
    update: bool = False,
    agents: list[str] | None = None,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        # Composition expressions are session-scope only (cannot be persisted).
        if "+" in name and scope != "session":
            raise ProfileError(
                "composition expressions cannot be persisted; use --scope session"
            )

        # --- Global: materialise / undo -----------------------------------
        if back or scope == "global":
            if manifest_path.is_file() and not yes_global:
                raise ProfileError(
                    "refusing to change global skills from inside a project; "
                    "pass --global to confirm"
                )
            if agents:
                unknown = [a for a in agents if a not in DEFAULT_GLOBAL_AGENTS]
                if unknown:
                    raise ProfileError(
                        f"unknown agent(s): {', '.join(unknown)}; "
                        f"supported: {', '.join(DEFAULT_GLOBAL_AGENTS)}"
                    )

            if back:
                prev = load_previous_global(home)
                if prev is None:
                    raise ProfileError("no previous global skill set to restore")
                prev_body, prev_active, prev_agents = prev
                _apply_global(
                    prev_active or "<previous>",
                    prev_body,
                    prev_active,
                    # Restore to the agents it was on (or the explicit --agent).
                    agents=agents or prev_agents or None,
                    project_root=project_root,
                    home=home,
                    dry_run=dry_run,
                    json_output=json_output,
                )
                return

            resolved_name, body = resolve_profile_target(name, home=home, update=update)
            _apply_global(
                resolved_name,
                body,
                resolved_name,
                agents=agents,
                project_root=project_root,
                home=home,
                dry_run=dry_run,
                json_output=json_output,
            )
            return

        # --- Session: print the export line -------------------------------
        if scope == "session":
            typer.echo(f"export {ENV_VAR}={name}")
            typer.echo(
                f"hint: eval the above in your shell to activate profile '{name}'",
                err=True,
            )
            return

        # --- Project: lightweight pointer ---------------------------------
        write_active_profile(name, scope, project_root, home=home)
        emit(
            {"profile": name, "scope": scope},
            json_output=json_output,
            human=f"active profile set to '{name}' (scope: {scope})",
        )

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
