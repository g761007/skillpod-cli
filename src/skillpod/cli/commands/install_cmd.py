"""`skillpod install` — run the installer pipeline."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer import install


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    report = run_with_exit_codes(
        lambda: install(project_root, manifest_path=manifest_path),
        json_output=json_output,
    )

    payload = {
        "ok": True,
        "installed": [
            {
                "name": s.name,
                "source": s.resolved.source_kind,
                "commit": s.resolved.commit,
                "url": s.resolved.url,
                "sha256": s.sha256,
                "path": str(s.project_path),
            }
            for s in report.installed
        ],
        "skipped": report.skipped,
        "satisfied_by_global": report.satisfied_by_global,
        "shadowed_by_global": report.shadowed_by_global,
        "agents": report.fanned_out_to,
    }
    if json_output:
        emit(payload, json_output=True)
        return

    lines: list[str] = []
    if report.installed:
        lines.append(f"Installed {len(report.installed)} skill(s):")
        for entry in report.installed:
            commit = entry.resolved.commit[:8] if entry.resolved.commit else "local"
            lines.append(f"  • {entry.name:<24} {entry.resolved.source_kind:<8} {commit}")
        if report.fanned_out_to:
            lines.append(f"Fanned out to: {', '.join(report.fanned_out_to)}")

    if report.skipped:
        lines.append(f"Already present: {len(report.skipped)} skill(s)")

    if report.satisfied_by_global:
        lines.append(
            f"Satisfied by your global install: {', '.join(report.satisfied_by_global)}"
        )

    # Only reachable with prefer_global: false. Saying nothing here would leave
    # the user with a project copy that their agent quietly ignores.
    for name, agents in sorted(report.shadowed_by_global.items()):
        lines.append(
            f"warning: '{name}' is also installed globally, and "
            f"{', '.join(agents)} prefer{'s' if len(agents) == 1 else ''} the "
            f"global copy — this project's version will not be the one in use. "
            f"Remove it from ~/.skillpod/skills/, or drop "
            f"`install.prefer_global: false`."
        )

    if not lines:
        lines.append("No skills declared in manifest.")

    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
