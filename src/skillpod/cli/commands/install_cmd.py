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
        "agents": report.fanned_out_to,
    }
    if json_output:
        emit(payload, json_output=True)
        return

    if not report.installed:
        emit(payload, json_output=False, human="No skills declared in manifest.")
        return

    lines = [f"Installed {len(report.installed)} skill(s):"]
    for entry in report.installed:
        commit = entry.resolved.commit[:8] if entry.resolved.commit else "local"
        lines.append(f"  • {entry.name:<24} {entry.resolved.source_kind:<8} {commit}")
    if report.fanned_out_to:
        lines.append(f"Fanned out to: {', '.join(report.fanned_out_to)}")
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
