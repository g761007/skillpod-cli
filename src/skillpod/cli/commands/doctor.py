"""`skillpod doctor` — verify manifest/lockfile/symlink consistency.

Checks performed (in order):
1. Every manifest skill (non-local-sourced) exists in skillfile.lock.
2. Every lockfile entry has a materialised directory at .skillpod/skills/<name>/.
3. Every .<agent>/skills/<name> symlink declared by the manifest resolves into
   .skillpod/skills/.
4. No directory under .skillpod/skills/ is absent from the manifest (orphan).

Exit codes:
    0  no error-severity findings (warnings OK)
    1  one or more error-severity findings
    2  filesystem unreadable / manifest missing
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from skillpod.cli._output import emit, fail
from skillpod.installer.expand import flatten
from skillpod.installer.paths import agent_skill_dir, install_root, is_managed_fanout
from skillpod.installer.user_skills import discover_user_skills
from skillpod.lockfile import io as lockfile_io
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SkillEntry


class Finding(TypedDict, total=False):
    severity: str  # "error" | "warning"
    code: str
    message: str
    path: str


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=2, json_output=json_output)

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    lockfile_path = project_root / "skillfile.lock"
    try:
        lock = lockfile_io.read(lockfile_path)
    except Exception as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    skills_root = install_root(project_root)
    findings: list[Finding] = []

    skills = flatten(manifest)
    user_skills = discover_user_skills(project_root)
    skill_names = {skill.name for skill in skills}
    for name in user_skills:
        if name not in skill_names:
            skills.append(SkillEntry(name=name))
            skill_names.add(name)

    # Determine which skills are local-sourced (not lockable).
    source_map = {s.name: s for s in manifest.sources}
    manifest_skill_names: set[str] = set()

    for skill in skills:
        manifest_skill_names.add(skill.name)

        # Check 1: every non-local manifest skill has a lockfile entry.
        # A skill is considered "local" when its declared source is explicitly
        # typed as local, OR when it has no lockfile entry but IS materialised
        # (meaning it was installed via a local source without being locked).
        is_local = False
        if skill.name in user_skills:
            is_local = True
        elif skill.source is not None:
            src = source_map.get(skill.source)
            if src is not None and src.type == "local":
                is_local = True
        else:
            # Implicit source: if the skill is materialised but not in the
            # lockfile it must be local-resolved (local sources are never locked).
            materialised = skills_root / skill.name
            if materialised.exists() and skill.name not in lock.resolved:
                is_local = True

        if not is_local and skill.name not in lock.resolved:
            findings.append(
                Finding(
                    severity="error",
                    code="missing-lock-entry",
                    message=f"skill '{skill.name}' is in the manifest but has no lockfile entry",
                )
            )

    # Check 2: every lockfile entry has a materialised directory.
    for name in lock.resolved:
        skill_dir = skills_root / name
        if not skill_dir.exists():
            findings.append(
                Finding(
                    severity="error",
                    code="missing-materialised-dir",
                    message=f"lockfile entry '{name}' has no materialised directory",
                    path=str(skill_dir),
                )
            )

    # Check 3: every declared agent fan-out symlink resolves into .skillpod/skills/.
    for skill in skills:
        for agent in manifest.agents:
            link = agent_skill_dir(project_root, agent, skill.name)
            if not link.exists() and not link.is_symlink():
                findings.append(
                    Finding(
                        severity="error",
                        code="missing-fanout-symlink",
                        message=f"fan-out symlink for '{skill.name}' under .{agent}/skills/ is missing",
                        path=str(link),
                    )
                )
            elif link.is_symlink() and not is_managed_fanout(link, project_root):
                findings.append(
                    Finding(
                        severity="error",
                        code="unmanaged-fanout-symlink",
                        message=(
                            f"fan-out symlink for '{skill.name}' under .{agent}/skills/ "
                            f"does not point into .skillpod/skills/"
                        ),
                        path=str(link),
                    )
                )

    # Check 4: orphan directories under .skillpod/skills/ not in manifest.
    try:
        if skills_root.exists():
            for child in skills_root.iterdir():
                if child.name not in manifest_skill_names:
                    findings.append(
                        Finding(
                            severity="warning",
                            code="orphan-dir",
                            message=f"'{child.name}' under .skillpod/skills/ is not in the manifest",
                            path=str(child),
                        )
                    )
    except OSError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    has_errors = any(f["severity"] == "error" for f in findings)
    ok = not has_errors

    payload = {"ok": ok, "findings": list(findings)}
    if json_output:
        emit(payload, json_output=True)
        if not ok:
            raise SystemExit(1)
        return

    if not findings:
        emit(payload, json_output=False, human="No findings. Project looks healthy.")
    else:
        lines: list[str] = []
        for f in findings:
            path_suffix = f" ({f['path']})" if f.get("path") else ""
            lines.append(f"[{f['severity'].upper()}] {f['code']}: {f['message']}{path_suffix}")
        emit(payload, json_output=False, human="\n".join(lines))

    if not ok:
        raise SystemExit(1)


__all__ = ["run"]
