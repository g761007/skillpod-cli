"""`skillpod update [skill]` — re-resolve and refresh the lockfile.

Force re-resolve mode: drop the matching lockfile entry (or all entries when
no name is given) so resolution proceeds from scratch through the registry or
declared sources.  Trust enforcement applies because it is wired into the
resolve step (Phase B §1).

On any failure the lockfile is restored from a snapshot taken before the
operation, leaving the project in its previous state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer import install
from skillpod.lockfile import io as lockfile_io
from skillpod.lockfile.models import Lockfile


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str | None,
    json_output: bool,
) -> None:
    lockfile_path = project_root / "skillfile.lock"

    # Snapshot the current lockfile so we can restore it on failure.
    existing_lock = lockfile_io.read(lockfile_path)
    snapshot_resolved = dict(existing_lock.resolved)

    # Build the trimmed lockfile (drop target entry/entries so the installer
    # re-resolves from scratch instead of pinning the cached commit).
    if skill_name is None:
        trimmed = Lockfile(version=1, resolved={})
    else:
        if skill_name not in existing_lock.resolved:
            # Skill not locked yet — still attempt install (it might be new).
            trimmed = existing_lock
        else:
            new_resolved = {k: v for k, v in existing_lock.resolved.items() if k != skill_name}
            trimmed = Lockfile(version=1, resolved=new_resolved)

    # Write the trimmed lockfile so the installer sees no pin for the target.
    try:
        lockfile_io.write(lockfile_path, trimmed)
    except OSError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    try:
        report = run_with_exit_codes(
            lambda: install(project_root, manifest_path=manifest_path),
            json_output=json_output,
        )
    except (typer.Exit, SystemExit):
        # run_with_exit_codes raised typer.Exit — restore lockfile then re-raise.
        _restore(lockfile_path, snapshot_resolved)
        raise

    updated: list[dict[str, str | None]] = [
        {
            "name": s.name,
            "commit": s.resolved.commit,
            "url": s.resolved.url,
        }
        for s in report.installed
        if skill_name is None or s.name == skill_name
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


def _restore(lockfile_path: Path, resolved: Any) -> None:
    """Best-effort restore of the lockfile snapshot; ignore errors."""
    try:
        from skillpod.lockfile.models import Lockfile as _Lockfile
        lockfile_io.write(lockfile_path, _Lockfile(version=1, resolved=resolved))
    except Exception:
        pass


__all__ = ["run"]
