"""`skillpod global update [skill...]` — refresh globally installed skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer.global_update import UpdatePlan, execute_update, plan_update


def _plan_lines(plan: UpdatePlan, unknown_names: list[str]) -> list[str]:
    lines: list[str] = []
    if unknown_names:
        lines.append(f"not installed: {', '.join(unknown_names)}")
    for name, reason in plan.unreachable:
        lines.append(f"  unreachable  {name:<28} {reason}")
    if plan.skipped_local:
        lines.append(
            f"  local        {len(plan.skipped_local)} skill(s) — no upstream to pull from"
        )
    if plan.skipped_unknown:
        lines.append(
            f"  no source    {len(plan.skipped_unknown)} skill(s) — origin unknown, "
            "reinstall from a source to make them updatable"
        )
    if plan.current:
        lines.append(f"  up to date   {len(plan.current)} skill(s)")
    return lines


def run(
    *,
    skills: list[str] | None,
    dry_run: bool,
    json_output: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        plan, unknown_names = plan_update(
            names=skills, home=home, persist_record=not dry_run
        )

        payload: dict[str, Any] = {
            "ok": True,
            "dry_run": dry_run,
            "not_installed": unknown_names,
            "pending": [
                {
                    "name": u.name,
                    "from": u.from_commit,
                    "to": u.to_commit,
                    "ref": u.ref,
                }
                for u in plan.to_update
            ],
            "up_to_date": plan.current,
            "skipped_local": plan.skipped_local,
            "skipped_unknown": plan.skipped_unknown,
            "unreachable": [{"name": n, "reason": r} for n, r in plan.unreachable],
        }

        if dry_run or not plan.has_work:
            head = (
                f"Would update {len(plan.to_update)} skill(s):"
                if dry_run and plan.has_work
                else "Everything is up to date."
                if not plan.has_work
                else ""
            )
            lines = [head] if head else []
            lines += [
                f"  {u.name:<28} {u.from_commit[:12]} → {u.to_commit[:12]}"
                for u in plan.to_update
            ]
            lines += _plan_lines(plan, unknown_names)
            emit(payload, json_output=json_output, human="\n".join(lines))
            return

        report = execute_update(plan, home=home)
        payload["updated"] = [
            {"name": u.name, "from": u.from_commit, "to": u.to_commit}
            for u in report.updated
        ]
        payload["failed"] = [{"name": n, "reason": r} for n, r in report.failed]
        payload["ok"] = not report.failed

        lines = [f"Updated {len(report.updated)} skill(s):"] if report.updated else []
        lines += [
            f"  {u.name:<28} {u.from_commit[:12]} → {u.to_commit[:12]}"
            for u in report.updated
        ]
        for name, reason in report.failed:
            lines.append(f"  failed       {name:<28} {reason}")
        lines += _plan_lines(plan, unknown_names)
        emit(payload, json_output=json_output, human="\n".join(lines))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
