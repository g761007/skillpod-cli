"""`skillpod outdated` — diff lockfile commits against latest upstream.

Simplification (documented here): the lockfile does not record whether a skill
was installed via the registry or an explicit git source.  Every locked entry
carries a ``url`` that is a valid git remote, so this command uses
``git ls-remote --exit-code <url> HEAD`` uniformly for all entries.
The user-visible output is identical regardless of the original source kind.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, fail
from skillpod.lockfile import io as lockfile_io
from skillpod.sources.errors import GitOperationError


def _latest_commit(url: str) -> str:
    """Return the current HEAD SHA from ``url`` via git ls-remote."""
    try:
        result = subprocess.run(
            ("git", "ls-remote", "--exit-code", url, "HEAD"),
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise GitOperationError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitOperationError(
            f"git ls-remote failed for {url!r} (exit {exc.returncode}): {exc.stderr.strip()}"
        ) from exc

    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    sha, _, _ = first_line.partition("\t")
    if len(sha) != 40:
        raise GitOperationError(f"git ls-remote returned unexpected output for {url!r}: {sha!r}")
    return sha


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
) -> None:
    lockfile_path = project_root / "skillfile.lock"
    lock = lockfile_io.read(lockfile_path)

    if not lock.resolved:
        payload = {"ok": True, "skills": []}
        emit(payload, json_output=json_output, human="No locked skills.")
        return

    rows: list[dict[str, Any]] = []
    try:
        for name, locked in lock.resolved.items():
            latest = _latest_commit(locked.url)
            rows.append(
                {
                    "name": name,
                    "locked": locked.commit,
                    "latest": latest,
                    "drift": locked.commit != latest,
                }
            )
    except GitOperationError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    payload = {"ok": True, "skills": rows}
    if json_output:
        emit(payload, json_output=True)
        return

    if not rows:
        emit(payload, json_output=False, human="No locked skills.")
        return

    col_headers = ["name", "locked-commit", "latest-commit", "drift"]
    rows_display = [
        [
            r["name"],
            r["locked"][:12],
            r["latest"][:12],
            "yes" if r["drift"] else "no",
        ]
        for r in rows
    ]

    widths = [len(h) for h in col_headers]
    for row in rows_display:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt(cells: list[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    lines = [_fmt(col_headers)]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows_display:
        lines.append(_fmt(row))

    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
