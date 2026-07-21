"""`skillpod outdated` — diff recorded commits against latest upstream.

Every git-backed record entry carries a ``source`` that is a valid git remote,
so this command uses ``git ls-remote --exit-code <url> HEAD`` uniformly and the
user-visible output is identical regardless of the original source kind.

Entries with nothing to compare against — local sources, and skills whose
provenance could not be recovered — are skipped rather than reported as
drifted. Drift is unknowable for them, and claiming otherwise would be a lie.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, fail
from skillpod.installer.paths import project_record_path
from skillpod.record import io as record_io
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
    installed = record_io.read(project_record_path(project_root)).installed
    comparable = {
        name: rec
        for name, rec in installed.items()
        if rec.kind in ("git", "registry") and rec.source and rec.commit
    }

    if not comparable:
        payload = {"ok": True, "skills": []}
        emit(payload, json_output=json_output, human="No git-backed skills installed.")
        return

    rows: list[dict[str, Any]] = []
    try:
        for name, rec in comparable.items():
            assert rec.source is not None  # narrowed by `comparable`
            latest = _latest_commit(rec.source)
            rows.append(
                {
                    "name": name,
                    "installed": rec.commit,
                    "latest": latest,
                    "drift": rec.commit != latest,
                }
            )
    except GitOperationError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    payload = {"ok": True, "skills": rows}
    if json_output:
        emit(payload, json_output=True)
        return

    if not rows:
        emit(payload, json_output=False, human="No git-backed skills installed.")
        return

    col_headers = ["name", "installed", "latest", "drift"]
    rows_display = [
        [
            r["name"],
            r["installed"][:12],
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
