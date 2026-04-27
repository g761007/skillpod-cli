"""`skillpod global doctor` — advisory checks for global skill dirs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from skillpod.cli._output import emit, fail
from skillpod.cli.commands.global_list import known_global_roots, scan_global_skills
from skillpod.lockfile import io as lockfile_io


class GlobalFinding(TypedDict, total=False):
    severity: str
    code: str
    message: str
    name: str
    paths: list[str]
    path: str


def _broken_symlinks() -> list[GlobalFinding]:
    findings: list[GlobalFinding] = []
    for _agent, root in known_global_roots():
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            if child.is_symlink() and not child.exists():
                findings.append(
                    GlobalFinding(
                        severity="error",
                        code="broken-global-symlink",
                        message=f"global skill symlink '{child.name}' is broken",
                        name=child.name,
                        path=str(child),
                    )
                )
    return findings


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    rows = scan_global_skills()
    findings: list[GlobalFinding] = []

    by_name: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_name[row["name"]].append(row["path"])

    for name, paths in sorted(by_name.items()):
        if len(paths) > 1:
            findings.append(
                GlobalFinding(
                    severity="warning",
                    code="duplicate-global-skill",
                    message=f"global skill '{name}' is installed for multiple agents",
                    name=name,
                    paths=paths,
                )
            )

    try:
        lock = lockfile_io.read(project_root / "skillfile.lock")
    except Exception as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    for name in sorted(set(by_name) & set(lock.resolved)):
        findings.append(
            GlobalFinding(
                severity="error",
                code="global-local-conflict",
                message=f"global skill '{name}' also exists in the current project lockfile",
                name=name,
                paths=by_name[name],
            )
        )

    findings.extend(_broken_symlinks())
    ok = not any(finding["severity"] == "error" for finding in findings)
    payload = {"ok": ok, "findings": findings}

    if json_output:
        emit(payload, json_output=True)
        if not ok:
            raise SystemExit(1)
        return

    if not findings:
        emit(payload, json_output=False, human="No global findings.")
    else:
        lines = []
        for finding in findings:
            location = ""
            if "paths" in finding:
                location = " (" + ", ".join(finding["paths"]) + ")"
            elif "path" in finding:
                location = f" ({finding['path']})"
            lines.append(
                f"[{finding['severity'].upper()}] {finding['code']}: "
                f"{finding['message']}{location}"
            )
        emit(payload, json_output=False, human="\n".join(lines))

    if not ok:
        raise SystemExit(1)


__all__ = ["GlobalFinding", "run"]
