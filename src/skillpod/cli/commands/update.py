"""`skillpod update [skill]` — refresh installed skills to newer upstream content.

`install` deliberately leaves an already-installed skill alone. `update` is
the explicit opposite: re-resolve against the source's ref and re-materialise
whatever moved. That split is what makes `install` cheap and predictable while
still giving the user a way to ask for something newer.

It delegates to the same pipeline via ``refresh=``, so there is one install
path rather than two that can drift apart.

The install record is written only after materialisation succeeds, so a failed
update leaves the previous record intact — no snapshot/restore dance needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, run_with_exit_codes
from skillpod.installer import install


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str | None,
    json_output: bool,
) -> None:
    refresh: bool | list[str] = True if skill_name is None else [skill_name]

    report = run_with_exit_codes(
        lambda: install(project_root, manifest_path=manifest_path, refresh=refresh),
        json_output=json_output,
    )

    # `report.installed` holds exactly what was (re)resolved this run; skills
    # left alone are in `report.skipped`.
    updated: list[dict[str, str | None]] = [
        {
            "name": s.name,
            "commit": s.resolved.commit,
            "url": s.resolved.url,
        }
        for s in report.installed
    ]
    payload: dict[str, Any] = {"ok": True, "updated": updated}
    if json_output:
        emit(payload, json_output=True)
        return

    if not updated:
        emit(payload, json_output=False, human="Nothing to update.")
        return

    lines = [f"Updated {len(updated)} skill(s):"]
    for entry in updated:
        commit = (entry["commit"] or "")[:12]
        lines.append(f"  {entry['name']:<24} {commit}")
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
